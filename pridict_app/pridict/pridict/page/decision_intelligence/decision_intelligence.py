"""Decision Intelligence page controller."""
import frappe


def get_context(context):
	context.no_cache = 1
