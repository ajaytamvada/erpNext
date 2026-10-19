"""Procurement Assistant page controller (buyer-facing chat)."""
import frappe


def get_context(context):
	context.no_cache = 1
