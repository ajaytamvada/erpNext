"""Approval Inbox page controller (Agent Studio)."""
import frappe


def get_context(context):
	context.no_cache = 1
