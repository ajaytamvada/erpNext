from pathlib import Path

import frappe

from pridict import __version__


SUPPORT_EMAIL = "pavan@riditstack.com"
NOTICES_ROUTE = "/pridict-notices"
RELEASE_NOTES_ROUTE = "/pridict-release-notes"


def get_notices_context(context):
	context.no_cache = 1
	context.title = frappe._("Pridict notices")
	context.support_email = SUPPORT_EMAIL
	context.pridict_version = __version__
	context.repository_notices = _repository_notices_available()
	return context


def get_release_notes_context(context):
	context.no_cache = 1
	context.title = frappe._("Pridict release notices")
	context.support_email = SUPPORT_EMAIL
	context.pridict_version = __version__
	return context


def _repository_notices_available():
	repository_root = Path(__file__).resolve().parents[2]
	return all((repository_root / filename).exists() for filename in ("license.txt", "attributions.md"))
