from __future__ import annotations

import hashlib
import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from pridict.schema_intelligence.normalization import canonical_json

from pridict.process_intelligence.models import ProcessModel


class ProcessModelNotFoundError(KeyError):
	pass


class ProcessModelIntegrityError(ValueError):
	pass


def compute_process_hash(model: ProcessModel) -> str:
	return hashlib.sha256(canonical_json(model.deterministic_dict()).encode()).hexdigest()


class ProcessModelRepository(ABC):
	@abstractmethod
	def save(self, model: ProcessModel) -> None: ...

	@abstractmethod
	def load(self, process_id: str) -> ProcessModel: ...

	@abstractmethod
	def list_ids(self) -> list[str]: ...


class InMemoryProcessModelRepository(ProcessModelRepository):
	def __init__(self):
		self._models: dict[str, ProcessModel] = {}

	def save(self, model: ProcessModel) -> None:
		self._models[model.process_id] = model

	def load(self, process_id: str) -> ProcessModel:
		try:
			return self._models[process_id]
		except KeyError as exc:
			raise ProcessModelNotFoundError(process_id) from exc

	def list_ids(self) -> list[str]:
		return sorted(self._models)


class FilesystemProcessModelRepository(ProcessModelRepository):
	def __init__(self, root: str | Path):
		self.root = Path(root)

	def save(self, model: ProcessModel) -> None:
		self.root.mkdir(parents=True, exist_ok=True)
		payload = {"content_hash": compute_process_hash(model), "model": model.to_dict()}
		serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
		descriptor, temporary_name = tempfile.mkstemp(prefix=f".{model.process_id}.", suffix=".tmp", dir=self.root)
		try:
			with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
				handle.write(serialized)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary_name, self._path(model.process_id))
		except Exception:
			if os.path.exists(temporary_name):
				os.unlink(temporary_name)
			raise

	def load(self, process_id: str) -> ProcessModel:
		path = self._path(process_id)
		if not path.is_file():
			raise ProcessModelNotFoundError(process_id)
		with path.open(encoding="utf-8") as handle:
			payload = json.load(handle)
		model = ProcessModel.from_dict(payload["model"])
		if payload.get("content_hash") != compute_process_hash(model):
			raise ProcessModelIntegrityError(f"process model {process_id} failed integrity validation")
		return model

	def list_ids(self) -> list[str]:
		if not self.root.is_dir():
			return []
		return sorted(path.stem for path in self.root.glob("*.json") if path.is_file())

	def _path(self, process_id: str) -> Path:
		allowed = "0123456789abcdefghijklmnopqrstuvwxyz-"
		if not process_id or any(character not in allowed for character in process_id.lower()):
			raise ValueError("process_id contains unsupported characters")
		return self.root / f"{process_id}.json"
