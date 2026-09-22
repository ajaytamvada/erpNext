from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


class UnsupportedValueError(TypeError):
	pass


def normalize_value(value: Any, path: str = "$") -> Any:
	if value is None or isinstance(value, str | bool | int):
		return value
	if isinstance(value, float):
		if value != value or value in (float("inf"), float("-inf")):
			return {"$type": "float", "value": repr(value)}
		return value
	if isinstance(value, Decimal):
		return {"$type": "decimal", "value": str(value)}
	if isinstance(value, datetime):
		return {
			"$type": "datetime",
			"value": value.isoformat(),
			"timezone": "aware" if value.tzinfo is not None else "naive",
		}
	if isinstance(value, date):
		return {"$type": "date", "value": value.isoformat()}
	if isinstance(value, time):
		return {
			"$type": "time",
			"value": value.isoformat(),
			"timezone": "aware" if value.tzinfo is not None else "naive",
		}
	if isinstance(value, timedelta):
		return {"$type": "timedelta", "microseconds": int(value.total_seconds() * 1_000_000)}
	if isinstance(value, bytes | bytearray | memoryview):
		return {"$type": "bytes", "base64": base64.b64encode(bytes(value)).decode("ascii")}
	if isinstance(value, UUID):
		return {"$type": "uuid", "value": str(value)}
	if isinstance(value, Path):
		return {"$type": "path", "value": str(value)}
	if isinstance(value, Enum):
		return {
			"$type": "enum",
			"class": f"{value.__class__.__module__}.{value.__class__.__qualname__}",
			"value": normalize_value(value.value, f"{path}.value"),
		}
	if isinstance(value, Mapping):
		return {
			str(key): normalize_value(item, f"{path}.{key}")
			for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
		}
	if isinstance(value, list):
		return [normalize_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
	if isinstance(value, tuple):
		return {
			"$type": "tuple",
			"items": [normalize_value(item, f"{path}[{index}]") for index, item in enumerate(value)],
		}
	if isinstance(value, set | frozenset):
		items = [normalize_value(item, f"{path}[]") for item in value]
		items.sort(key=canonical_json)
		return {"$type": "set", "items": items}
	raise UnsupportedValueError(f"unsupported value at {path}: {type(value).__module__}.{type(value).__name__}")


def canonical_json(value: Any) -> str:
	return json.dumps(normalize_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def optional_bool(value: Any) -> bool | None:
	if value is None:
		return None
	if isinstance(value, str):
		if value.strip() == "":
			return False
		if value.strip().lower() in ("0", "false", "no"):
			return False
		if value.strip().lower() in ("1", "true", "yes"):
			return True
	return bool(value)
