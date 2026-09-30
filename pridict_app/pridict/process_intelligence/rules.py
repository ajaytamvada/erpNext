from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConditionRepresentation:
	expression: str | None
	support: str
	note: str


def represent_condition(expression: object, *, executable_source: bool = False) -> ConditionRepresentation:
	if expression is None or not str(expression).strip():
		return ConditionRepresentation(None, "NO_CONDITION", "No configured condition was found.")
	text = str(expression).strip()
	if executable_source:
		return ConditionRepresentation(
			text,
			"UNSUPPORTED_EXECUTABLE_RULE",
			"Executable source was recorded by locator and hash but was not executed or interpreted.",
		)
	return ConditionRepresentation(
		text,
		"RECORDED_NOT_EXECUTED",
		"The configured expression is preserved verbatim as data and is not executed.",
	)
