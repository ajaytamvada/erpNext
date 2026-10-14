"""Gateway tests with the HTTP layer mocked (no real provider is called)."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from pridict.agent_studio import gateway

AZURE = "_Test Azure Gateway"
LOCAL = "_Test Local Gateway"
SECRET = "sk-test-secret-123"


class FakeResponse:
	def __init__(self, status=200, payload=None, headers=None):
		self.status_code = status
		self.ok = 200 <= status < 300
		self._payload = payload or {}
		self.headers = headers or {}
		self.reason = "reason"
		self.text = json.dumps(self._payload)

	def json(self):
		return self._payload


def ok(content="OK", tool_calls=None, model="gpt-test"):
	message = {"role": "assistant", "content": content}
	if tool_calls:
		message["tool_calls"] = tool_calls
	return FakeResponse(
		200,
		{
			"model": model,
			"choices": [{"message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}],
			"usage": {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13},
		},
	)


def error(status, message="boom", param=None, headers=None):
	return FakeResponse(status, {"error": {"message": message, "param": param}}, headers)


class TestGateway(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name, values in (
			(
				AZURE,
				{
					"provider_type": "Azure OpenAI",
					"endpoint": "https://res.cognitiveservices.azure.com/",
					"api_version": "2025-04-01-preview",
					"api_key": SECRET,
				},
			),
			(LOCAL, {"provider_type": "OpenAI-compatible", "endpoint": "http://llm.local:8000/v1"}),
		):
			if not frappe.db.exists("LLM Provider", name):
				frappe.get_doc({"doctype": "LLM Provider", "provider_name": name, **values}).insert()
		cls.config("_gw-local", LOCAL, "llama")
		cls.config("_gw-azure", AZURE, "gpt-5.4-mini", fallback="_gw-local", retries=2)

	@classmethod
	def config(cls, name, provider, model, **extra):
		if frappe.db.exists("LLM Model Config", name):
			frappe.delete_doc("LLM Model Config", name, force=True)
		frappe.get_doc(
			{
				"doctype": "LLM Model Config",
				"config_name": name,
				"provider": provider,
				"model_id": model,
				"status": "Active",
				"temperature": 0.1,
				"max_tokens": 200,
				"timeout_s": 5,
				"retries": 0,
				**extra,
			}
		).insert()

	def setUp(self):
		frappe.cache().delete_value(gateway.UNSUPPORTED_CACHE_KEY)
		sleep = patch("pridict.agent_studio.gateway.time.sleep")
		sleep.start()
		self.addCleanup(sleep.stop)

	def post(self, *responses):
		mock = patch("pridict.agent_studio.gateway.requests.post", side_effect=list(responses)).start()
		self.addCleanup(patch.stopall)
		return mock

	def test_azure_request_shape(self):
		post = self.post(ok())
		response = gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		url, kwargs = post.call_args.args[0], post.call_args.kwargs
		self.assertEqual(
			url, "https://res.cognitiveservices.azure.com/openai/deployments/gpt-5.4-mini/chat/completions"
		)
		self.assertEqual(kwargs["params"], {"api-version": "2025-04-01-preview"})
		self.assertEqual(kwargs["headers"]["api-key"], SECRET)
		self.assertEqual(kwargs["json"]["max_completion_tokens"], 200)
		self.assertNotIn("model", kwargs["json"])
		self.assertEqual(response.content, "OK")
		self.assertEqual(response.usage.total_tokens, 13)

	def test_openai_compatible_request_shape(self):
		post = self.post(ok())
		gateway.chat("_gw-local", [{"role": "user", "content": "hi"}])
		url, kwargs = post.call_args.args[0], post.call_args.kwargs
		self.assertEqual(url, "http://llm.local:8000/v1/chat/completions")
		self.assertNotIn("Authorization", kwargs["headers"])
		self.assertEqual(kwargs["json"]["model"], "llama")
		self.assertEqual(kwargs["json"]["max_tokens"], 200)

	def test_retries_then_succeeds(self):
		post = self.post(error(429, headers={"Retry-After": "1"}), error(503), ok())
		response = gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		self.assertEqual(post.call_count, 3)
		self.assertEqual(response.attempts, 3)
		self.assertEqual(response.model_config, "_gw-azure")

	def test_falls_back_after_retries_exhausted(self):
		post = self.post(error(500), error(500), error(500), ok(model="llama"))
		response = gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		self.assertEqual(post.call_count, 4)
		self.assertEqual(response.model_config, "_gw-local")
		self.assertEqual(response.fallbacks[0]["config"], "_gw-azure")

	def test_auth_error_is_not_retried_but_falls_back(self):
		post = self.post(error(401, "Access denied"), ok())
		response = gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		self.assertEqual(post.call_count, 2)
		self.assertEqual(response.model_config, "_gw-local")

	def test_unsupported_temperature_is_dropped_and_remembered(self):
		rejected = error(
			400, "Unsupported value: 'temperature' does not support 0.1 with this model.", param="temperature"
		)
		post = self.post(rejected, ok(), ok())
		gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		self.assertIn("temperature", post.call_args_list[0].kwargs["json"])
		self.assertNotIn("temperature", post.call_args_list[1].kwargs["json"])
		gateway.chat("_gw-azure", [{"role": "user", "content": "again"}])
		self.assertNotIn("temperature", post.call_args_list[2].kwargs["json"])

	def test_timeout_is_retryable(self):
		self.post(requests.Timeout(), ok())
		self.assertEqual(gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}]).attempts, 2)

	def test_all_failures_raise_without_leaking_key(self):
		self.post(*[error(401, "bad key")] * 2)
		with self.assertRaises(gateway.LLMError) as caught:
			gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}])
		self.assertIn("_gw-azure", str(caught.exception))
		self.assertIn("_gw-local", str(caught.exception))
		self.assertNotIn(SECRET, str(caught.exception))

	def test_tool_calls_and_structured_output(self):
		call = {
			"id": "c1",
			"type": "function",
			"function": {"name": "search_items", "arguments": '{"query": "alu"}'},
		}
		post = self.post(ok(content=None, tool_calls=[call]))
		tools = [
			{
				"name": "search_items",
				"description": "find",
				"parameters": {"type": "object", "properties": {}},
			}
		]
		schema = {
			"title": "Sourcing Plan",
			"type": "object",
			"properties": {},
			"required": [],
			"additionalProperties": False,
		}
		response = gateway.chat(
			"_gw-local", [{"role": "user", "content": "hi"}], tools=tools, response_schema=schema
		)
		body = post.call_args.kwargs["json"]
		self.assertEqual(body["tools"][0]["function"]["name"], "search_items")
		self.assertEqual(body["response_format"]["json_schema"]["name"], "Sourcing_Plan")
		self.assertEqual(response.tool_calls[0].arguments, {"query": "alu"})
		self.assertEqual(response.assistant_message()["tool_calls"][0]["id"], "c1")

	def test_disabled_config_is_skipped_to_fallback(self):
		frappe.db.set_value("LLM Model Config", "_gw-azure", "status", "Disabled")
		frappe.clear_document_cache("LLM Model Config", "_gw-azure")
		self.addCleanup(
			lambda: (
				frappe.db.set_value("LLM Model Config", "_gw-azure", "status", "Active"),
				frappe.clear_document_cache("LLM Model Config", "_gw-azure"),
			)
		)
		post = self.post(ok())
		self.assertEqual(
			gateway.chat("_gw-azure", [{"role": "user", "content": "hi"}]).model_config, "_gw-local"
		)
		self.assertEqual(post.call_count, 1)

	def test_test_provider_records_status(self):
		self.post(ok())
		result = gateway.test_provider(AZURE)
		self.assertTrue(result["ok"])
		self.assertEqual(frappe.db.get_value("LLM Provider", AZURE, "status"), "Connected")
		self.post(error(401, "bad key"))
		result = gateway.test_provider(AZURE)
		self.assertFalse(result["ok"])
		self.assertEqual(frappe.db.get_value("LLM Provider", AZURE, "status"), "Failed")
		self.assertNotIn(SECRET, frappe.db.get_value("LLM Provider", AZURE, "last_error"))
