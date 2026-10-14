from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document

# Fields that invalidate a previous connection test when they change.
CONNECTION_FIELDS = ("provider_type", "endpoint", "api_version", "api_key")


class LLMProvider(Document):
	def validate(self):
		self.endpoint = (self.endpoint or "").strip()
		parsed = urlparse(self.endpoint)
		if parsed.scheme not in ("http", "https") or not parsed.netloc:
			frappe.throw(
				_("Endpoint must be a full URL, for example https://my-resource.cognitiveservices.azure.com/")
			)
		if parsed.scheme == "http" and self.provider_type != "OpenAI-compatible":
			frappe.throw(_("Only OpenAI-compatible (self-hosted) providers may use a plain http endpoint."))
		if self.provider_type == "Azure OpenAI":
			self.api_version = (self.api_version or "").strip()
			if not self.api_version:
				frappe.throw(_("API Version is required for Azure OpenAI, for example 2025-04-01-preview."))
		else:
			self.api_version = None

		previous = self.get_doc_before_save()
		if previous and any(previous.get(field) != self.get(field) for field in CONNECTION_FIELDS):
			self.status = "Not tested"
			self.last_error = None
