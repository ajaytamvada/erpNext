"""Outbound HTTP for automations, with the guards of design Section 13.

- Only http and https.
- Only hosts on the site's allowlist (Automation Settings); an empty list allows nothing.
- Every address the host resolves to must be public: private, loopback, link-local, reserved
  and multicast ranges are refused, so a URL cannot reach the server itself or the network
  behind it (SSRF). The HTTP library resolves the host again when it connects, so a host that
  changes its DNS answer in between could still point elsewhere; the allowlist (hosts an
  administrator chose) is the main control and this check is the second line.
- Redirects are not followed.
"""

from __future__ import annotations

import ipaddress
import socket
from fnmatch import fnmatch
from urllib.parse import urlsplit

import requests
from frappe import _

MAX_RESPONSE_BYTES = 1_000_000
ALLOWED_SCHEMES = ("http", "https")


class OutboundError(Exception):
	pass


def allowlist(text: str | None) -> list[str]:
	return [
		line.strip().lower()
		for line in (text or "").splitlines()
		if line.strip() and not line.startswith("#")
	]


def host_allowed(host: str, patterns: list[str]) -> bool:
	host = (host or "").lower().rstrip(".")
	return any(fnmatch(host, pattern) for pattern in patterns)


def check_url(url: str, patterns: list[str]) -> tuple[str, str]:
	"""Return (host, a checked public IP) for the URL, or raise OutboundError."""
	parts = urlsplit(url or "")
	if parts.scheme not in ALLOWED_SCHEMES:
		raise OutboundError(_("Only http and https addresses can be called."))
	host = (parts.hostname or "").lower()
	if not host:
		raise OutboundError(_("The address has no host name."))
	if parts.username or parts.password:
		raise OutboundError(_("Put credentials in an Automation Credential, not in the address."))
	if not host_allowed(host, patterns):
		raise OutboundError(_("{0} is not on the list of allowed hosts (Automation Settings).").format(host))
	try:
		infos = socket.getaddrinfo(
			host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP
		)
	except socket.gaierror as error:
		raise OutboundError(_("Cannot find {0}: {1}").format(host, error)) from error
	addresses = {info[4][0] for info in infos}
	for address in addresses:
		ip = ipaddress.ip_address(address.split("%")[0])
		if not ip.is_global or ip.is_multicast:
			raise OutboundError(
				_("{0} points to a private or local address; that is not allowed.").format(host)
			)
	return host, sorted(addresses)[0]


def send(method: str, url: str, *, headers: dict, body=None, timeout: int, patterns: list[str]) -> dict:
	"""Make one request after checking the URL. Returns {status, headers, body}."""
	check_url(url, patterns)
	kwargs = {"headers": headers, "timeout": timeout, "allow_redirects": False, "stream": True}
	if body is not None:
		kwargs["json" if isinstance(body, dict | list) else "data"] = body
	try:
		response = requests.request(method, url, **kwargs)
	except requests.RequestException as error:
		raise OutboundError(_("The request failed: {0}").format(error)) from error
	content = b""
	for chunk in response.iter_content(65536):
		content += chunk
		if len(content) > MAX_RESPONSE_BYTES:
			response.close()
			raise OutboundError(_("The response is larger than 1 MB."))
	text = content.decode(response.encoding or "utf-8", errors="replace")
	parsed = text
	if "json" in (response.headers.get("Content-Type") or ""):
		try:
			parsed = response.json() if content else None
		except ValueError:
			parsed = text
	return {
		"status": response.status_code,
		"headers": {
			k: v
			for k, v in response.headers.items()
			if k.lower() in ("content-type", "location", "retry-after")
		},
		"body": parsed,
	}
