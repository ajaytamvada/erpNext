from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from pridict.schema_intelligence.normalization import canonical_json

from pridict.process_intelligence.transaction_models import ReconstructionResult


def compute_reconstruction_hash(result: ReconstructionResult) -> str:
	return hashlib.sha256(canonical_json(result.deterministic_dict()).encode()).hexdigest()


class FilesystemReconstructionRepository:
	def __init__(self, root: str | Path):
		self.root = Path(root)

	def save(self, result: ReconstructionResult) -> None:
		self.root.mkdir(parents=True, exist_ok=True)
		payload = {"content_hash": compute_reconstruction_hash(result), "result": result.to_dict()}
		descriptor, temporary_name = tempfile.mkstemp(
			prefix=f".{result.reconstruction_id}.",
			suffix=".tmp",
			dir=self.root,
		)
		try:
			with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
				json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
				handle.write("\n")
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary_name, self._path(result.reconstruction_id))
		except Exception:
			if os.path.exists(temporary_name):
				os.unlink(temporary_name)
			raise

	def load(self, reconstruction_id: str) -> ReconstructionResult:
		path = self._path(reconstruction_id)
		if not path.is_file():
			raise KeyError(reconstruction_id)
		with path.open(encoding="utf-8") as handle:
			payload = json.load(handle)
		result = ReconstructionResult.from_dict(payload["result"])
		if payload.get("content_hash") != compute_reconstruction_hash(result):
			raise ValueError(f"reconstruction {reconstruction_id} failed integrity validation")
		return result

	def list_ids(self) -> list[str]:
		if not self.root.is_dir():
			return []
		return sorted(path.stem for path in self.root.glob("*.json") if path.is_file())

	def _path(self, reconstruction_id: str) -> Path:
		allowed = "0123456789abcdefghijklmnopqrstuvwxyz-"
		if not reconstruction_id or any(character not in allowed for character in reconstruction_id.lower()):
			raise ValueError("reconstruction_id contains unsupported characters")
		return self.root / f"{reconstruction_id}.json"
