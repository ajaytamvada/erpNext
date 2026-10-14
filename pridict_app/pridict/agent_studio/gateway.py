"""Provider-agnostic LLM gateway for Agent Studio.

Every model call goes through chat(): it resolves an LLM Model Config, applies its
timeout and retry settings, walks the fallback chain on failure, and returns a
normalised LLMResponse with token usage. API keys never appear in errors or logs.

Azure OpenAI, OpenAI and OpenAI-compatible servers share the chat-completions
protocol, so one adapter serves all three.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field

import frappe
import requests
from frappe import _

# Remember per provider+model that a parameter is rejected, so later calls skip it.
UNSUPPORTED_CACHE_KEY = "agent_studio_unsupported_params"
CONNECT_TIMEOUT_S = 10
MAX_BACKOFF_S = 20
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMError(Exception):
	def __init__(self, message: str, *, status: int | None = None, retryable: bool = False, config: str = ""):
		super().__init__(message)
		self.status = status
		self.retryable = retryable
		self.config = config


@dataclass
class ToolCall:
	id: str
	name: str
	arguments: dict


@dataclass
class Usage:
	prompt_tokens: int = 0
	completion_tokens: int = 0
	total_tokens: int = 0

	def add(self, other: Usage) -> None:
		self.prompt_tokens += other.prompt_tokens
		self.completion_tokens += other.completion_tokens
		self.total_tokens += other.total_tokens


@dataclass
class LLMResponse:
	content: str | None
	tool_calls: list[ToolCall]
	finish_reason: str | None
	usage: Usage
	model_config: str
	model: str
	latency_ms: int
	attempts: int = 1
	# Configs that failed before this one answered, with the reason.
	fallbacks: list[dict] = field(default_factory=list)

	def json(self) -> dict:
		"""Parse content as JSON (for structured-output calls)."""
		try:
			return json.loads(self.content or "")
		except ValueError as error:
			raise LLMError(_("The model did not return valid JSON."), config=self.model_config) from error

	def assistant_message(self) -> dict:
		"""The assistant turn to append to messages before sending tool results back."""
		message = {"role": "assistant", "content": self.content}
		if self.tool_calls:
			message["tool_calls"] = [
				{
					"id": c.id,
					"type": "function",
					"function": {"name": c.name, "arguments": json.dumps(c.arguments)},
				}
				for c in self.tool_calls
			]
		return message


@dataclass
class _Target:
	config: str
	provider: str
	provider_type: str
	endpoint: str
	api_version: str | None
	api_key: str | None
	model_id: str
	temperature: float | None
	max_tokens: int
	timeout_s: int
	retries: int
	reasoning_effort: str | None
	fallback: str | None


def _load_target(config_name: str) -> _Target:
	config = frappe.get_cached_doc("LLM Model Config", config_name)
	if config.status == "Disabled":
		raise LLMError(_("Model configuration {0} is disabled.").format(config_name), config=config_name)
	provider = frappe.get_doc("LLM Provider", config.provider)
	if not provider.enabled:
		raise LLMError(_("Provider {0} is disabled.").format(provider.name), config=config_name)
	if provider.provider_type == "Anthropic":
		raise LLMError(_("Anthropic providers are not supported by the gateway yet."), config=config_name)
	api_key = provider.get_password("api_key", raise_exception=False)
	if not api_key and provider.provider_type != "OpenAI-compatible":
		raise LLMError(
			_("Provider {0} has no API key. Add it on the provider record.").format(provider.name),
			config=config_name,
		)
	return _Target(
		config=config.name,
		provider=provider.name,
		provider_type=provider.provider_type,
		endpoint=provider.endpoint.rstrip("/"),
		api_version=provider.api_version,
		api_key=api_key,
		model_id=config.model_id,
		temperature=config.temperature,
		max_tokens=config.max_tokens or 1024,
		timeout_s=config.timeout_s or 60,
		retries=max(config.retries or 0, 0),
		reasoning_effort=config.reasoning_effort or None,
		fallback=config.fallback,
	)


def _request_parts(target: _Target) -> tuple[str, dict, dict]:
	"""URL, headers and query params for a chat-completions call."""
	headers = {"Content-Type": "application/json"}
	if target.provider_type == "Azure OpenAI":
		base = target.endpoint if target.endpoint.endswith("/openai") else f"{target.endpoint}/openai"
		url = f"{base}/deployments/{target.model_id}/chat/completions"
		headers["api-key"] = target.api_key
		return url, headers, {"api-version": target.api_version}
	if target.api_key:
		headers["Authorization"] = f"Bearer {target.api_key}"
	return f"{target.endpoint}/chat/completions", headers, {}


def _unsupported(target: _Target) -> set[str]:
	return set(frappe.cache().hget(UNSUPPORTED_CACHE_KEY, f"{target.provider}:{target.model_id}") or [])


def _mark_unsupported(target: _Target, param: str) -> None:
	params = _unsupported(target) | {param}
	frappe.cache().hset(UNSUPPORTED_CACHE_KEY, f"{target.provider}:{target.model_id}", sorted(params))


def _build_body(
	target: _Target, messages, tools, tool_choice, response_schema, max_tokens, dropped=()
) -> dict:
	skip = _unsupported(target) | set(dropped)
	body: dict = {"messages": messages}
	if target.provider_type != "Azure OpenAI":
		body["model"] = target.model_id
	# Newer OpenAI models (incl. gpt-5.x and o-series) only accept max_completion_tokens.
	token_param = "max_tokens" if target.provider_type == "OpenAI-compatible" else "max_completion_tokens"
	body[token_param] = max_tokens or target.max_tokens
	if target.temperature is not None and "temperature" not in skip:
		body["temperature"] = target.temperature
	if target.reasoning_effort and "reasoning_effort" not in skip:
		body["reasoning_effort"] = target.reasoning_effort
	if tools:
		body["tools"] = [
			{
				"type": "function",
				"function": {
					"name": t["name"],
					"description": t.get("description", ""),
					"parameters": t["parameters"],
				},
			}
			for t in tools
		]
		if tool_choice:
			body["tool_choice"] = tool_choice
	if response_schema:
		body["response_format"] = {
			"type": "json_schema",
			"json_schema": {
				"name": re.sub(r"[^a-zA-Z0-9_-]", "_", response_schema.get("title", "response"))[:64],
				"schema": response_schema,
				"strict": True,
			},
		}
	return body


def _error_message(response: requests.Response) -> str:
	try:
		error = response.json().get("error") or {}
		message = error.get("message") if isinstance(error, dict) else str(error)
	except ValueError:
		message = response.text[:300]
	return f"HTTP {response.status_code}: {message or response.reason}"


def _rejected_param(response: requests.Response) -> str | None:
	"""Name of an optional parameter the model rejected, if that is why the call failed."""
	if response.status_code != 400:
		return None
	try:
		error = response.json().get("error") or {}
	except ValueError:
		return None
	param = error.get("param") if isinstance(error, dict) else None
	message = (error.get("message") or "").lower() if isinstance(error, dict) else ""
	for name in ("temperature", "reasoning_effort"):
		if param == name or (name in message and ("unsupported" in message or "not support" in message)):
			return name
	return None


def _parse(target: _Target, payload: dict, latency_ms: int, attempts: int) -> LLMResponse:
	choices = payload.get("choices") or []
	if not choices:
		raise LLMError(_("The model returned no answer."), config=target.config)
	message = choices[0].get("message") or {}
	if message.get("refusal"):
		raise LLMError(
			_("The model refused the request: {0}").format(message["refusal"]), config=target.config
		)
	tool_calls = []
	for call in message.get("tool_calls") or []:
		function = call.get("function") or {}
		try:
			arguments = json.loads(function.get("arguments") or "{}")
		except ValueError:
			arguments = {"_invalid_json": function.get("arguments")}
		tool_calls.append(ToolCall(id=call.get("id", ""), name=function.get("name", ""), arguments=arguments))
	usage = payload.get("usage") or {}
	return LLMResponse(
		content=message.get("content"),
		tool_calls=tool_calls,
		finish_reason=choices[0].get("finish_reason"),
		usage=Usage(
			prompt_tokens=usage.get("prompt_tokens", 0),
			completion_tokens=usage.get("completion_tokens", 0),
			total_tokens=usage.get("total_tokens", 0),
		),
		model_config=target.config,
		model=payload.get("model") or target.model_id,
		latency_ms=latency_ms,
		attempts=attempts,
	)


def _backoff(attempt: int, response: requests.Response | None) -> float:
	retry_after = response.headers.get("Retry-After") if response is not None else None
	if retry_after:
		try:
			return min(float(retry_after), MAX_BACKOFF_S)
		except ValueError:
			pass
	return min(2**attempt + random.random(), MAX_BACKOFF_S)


def _call_target(target: _Target, messages, tools, tool_choice, response_schema, max_tokens) -> LLMResponse:
	url, headers, params = _request_parts(target)
	attempt = 0
	dropped: set[str] = set()
	while True:
		attempt += 1
		body = _build_body(target, messages, tools, tool_choice, response_schema, max_tokens, dropped)
		started = time.monotonic()
		response = None
		try:
			response = requests.post(
				url, headers=headers, params=params, json=body, timeout=(CONNECT_TIMEOUT_S, target.timeout_s)
			)
		except requests.Timeout:
			error = LLMError(
				_("Timed out after {0}s.").format(target.timeout_s), retryable=True, config=target.config
			)
		except requests.RequestException as exc:
			# Exception text can include the URL but never headers, so the key stays out.
			error = LLMError(
				_("Could not reach the provider: {0}").format(type(exc).__name__),
				retryable=True,
				config=target.config,
			)
		else:
			latency_ms = int((time.monotonic() - started) * 1000)
			if response.ok:
				return _parse(target, response.json(), latency_ms, attempt)
			rejected = _rejected_param(response)
			if rejected and rejected in body:
				# Not a real failure: drop the optional parameter and retry straight away.
				dropped.add(rejected)
				_mark_unsupported(target, rejected)
				attempt -= 1
				continue
			error = LLMError(
				_error_message(response),
				status=response.status_code,
				retryable=response.status_code in RETRYABLE_STATUS,
				config=target.config,
			)
		if not error.retryable or attempt > target.retries:
			error.attempts = attempt
			raise error
		time.sleep(_backoff(attempt, response))


def chat(
	config_name: str,
	messages: list[dict],
	*,
	tools: list[dict] | None = None,
	tool_choice: str | dict | None = None,
	response_schema: dict | None = None,
	max_tokens: int | None = None,
) -> LLMResponse:
	"""Send a chat request using an LLM Model Config, falling back along its chain.

	tools: [{name, description, parameters (JSON Schema)}]
	response_schema: JSON Schema the answer must follow (strict structured output).
	"""
	failures: list[dict] = []
	seen: set[str] = set()
	current = config_name
	while current and current not in seen:
		seen.add(current)
		target = None
		try:
			target = _load_target(current)
			response = _call_target(target, messages, tools, tool_choice, response_schema, max_tokens)
			response.fallbacks = failures
			return response
		except LLMError as error:
			failures.append({"config": current, "error": str(error), "status": error.status})
			current = (
				target.fallback if target else frappe.db.get_value("LLM Model Config", current, "fallback")
			)
	summary = "; ".join(f"{f['config']}: {f['error']}" for f in failures)
	raise LLMError(_("All model configurations failed. {0}").format(summary), config=config_name)


# ---------------------------------------------------------------------------
# Desk actions


def _first_config_for(provider: str) -> str | None:
	for status in ("Active", "Testing"):
		name = frappe.db.get_value("LLM Model Config", {"provider": provider, "status": status}, "name")
		if name:
			return name
	return None


@frappe.whitelist(methods=["POST"])
def test_provider(name: str) -> dict:
	"""Send a tiny prompt through one of the provider's model configurations and record the result."""
	frappe.only_for("System Manager")
	provider = frappe.get_doc("LLM Provider", name)
	config = _first_config_for(name)
	result = {"ok": False, "provider": name, "config": config}
	if not config:
		result["error"] = _("Add an active or testing model configuration for this provider first.")
	else:
		started = time.monotonic()
		try:
			target = _load_target(config)
			target.retries = 0
			target.fallback = None
			response = _call_target(
				target, [{"role": "user", "content": "Reply with the single word OK."}], None, None, None, 256
			)
			result.update(
				ok=True,
				latency_ms=response.latency_ms,
				model=response.model,
				reply=(response.content or "").strip(),
			)
		except LLMError as error:
			result.update(error=str(error), latency_ms=int((time.monotonic() - started) * 1000))
	provider.db_set(
		{
			"status": "Connected" if result["ok"] else "Failed",
			"last_tested_at": frappe.utils.now_datetime(),
			"last_latency_ms": result.get("latency_ms", 0) if result["ok"] else 0,
			"last_error": None if result["ok"] else result["error"][:1000],
		},
		update_modified=False,
	)
	return result


@frappe.whitelist(methods=["POST"])
def send_test_prompt(config: str, prompt: str) -> dict:
	"""Run one prompt through a model configuration (with its retries and fallbacks)."""
	frappe.only_for("System Manager")
	prompt = (prompt or "").strip()[:4000]
	if not prompt:
		frappe.throw(_("Enter a prompt."))
	try:
		response = chat(config, [{"role": "user", "content": prompt}])
	except LLMError as error:
		return {"ok": False, "error": str(error)}
	return {
		"ok": True,
		"reply": response.content,
		"model_config": response.model_config,
		"model": response.model,
		"latency_ms": response.latency_ms,
		"attempts": response.attempts,
		"usage": response.usage.__dict__,
		"fallbacks": response.fallbacks,
		"finish_reason": response.finish_reason,
	}
