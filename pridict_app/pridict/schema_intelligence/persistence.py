from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from pridict.schema_intelligence.models import SchemaSnapshot
from pridict.schema_intelligence.snapshots import compute_metadata_hash


class SnapshotNotFoundError(KeyError):
	pass


class IncompleteSnapshotError(ValueError):
	pass


class SnapshotIntegrityError(ValueError):
	pass


class SnapshotRepository(ABC):
	@abstractmethod
	def save(self, snapshot: SchemaSnapshot, *, require_complete: bool = False) -> None: ...

	@abstractmethod
	def load(self, snapshot_id: str) -> SchemaSnapshot: ...

	@abstractmethod
	def list_ids(self) -> list[str]: ...

	@abstractmethod
	def delete(self, snapshot_id: str) -> None: ...


def validate_snapshot_integrity(snapshot: SchemaSnapshot) -> None:
	expected = compute_metadata_hash(snapshot.doctypes, snapshot.relationships)
	if snapshot.metadata_hash != expected:
		raise SnapshotIntegrityError(
			f"snapshot {snapshot.snapshot_id} metadata hash does not match its normalized content"
		)


class InMemorySnapshotRepository(SnapshotRepository):
	def __init__(self):
		self._snapshots: dict[str, SchemaSnapshot] = {}

	def save(self, snapshot: SchemaSnapshot, *, require_complete: bool = False) -> None:
		_validate_for_save(snapshot, require_complete=require_complete)
		self._snapshots[snapshot.snapshot_id] = snapshot

	def load(self, snapshot_id: str) -> SchemaSnapshot:
		try:
			return self._snapshots[snapshot_id]
		except KeyError as exc:
			raise SnapshotNotFoundError(snapshot_id) from exc

	def list_ids(self) -> list[str]:
		return sorted(self._snapshots)

	def delete(self, snapshot_id: str) -> None:
		if snapshot_id not in self._snapshots:
			raise SnapshotNotFoundError(snapshot_id)
		del self._snapshots[snapshot_id]


class FilesystemSnapshotRepository(SnapshotRepository):
	def __init__(self, root: str | Path):
		self.root = Path(root)

	def save(self, snapshot: SchemaSnapshot, *, require_complete: bool = False) -> None:
		_validate_for_save(snapshot, require_complete=require_complete)
		self.root.mkdir(parents=True, exist_ok=True)
		target = self._path(snapshot.snapshot_id)
		payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
		file_descriptor, temporary_name = tempfile.mkstemp(
			prefix=f".{snapshot.snapshot_id}.", suffix=".tmp", dir=self.root
		)
		try:
			with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
				handle.write(payload)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary_name, target)
		except Exception:
			if os.path.exists(temporary_name):
				os.unlink(temporary_name)
			raise

	def load(self, snapshot_id: str) -> SchemaSnapshot:
		path = self._path(snapshot_id)
		if not path.is_file():
			raise SnapshotNotFoundError(snapshot_id)
		with path.open(encoding="utf-8") as handle:
			snapshot = SchemaSnapshot.from_dict(json.load(handle))
		validate_snapshot_integrity(snapshot)
		return snapshot

	def list_ids(self) -> list[str]:
		if not self.root.is_dir():
			return []
		return sorted(path.stem for path in self.root.glob("*.json") if path.is_file())

	def delete(self, snapshot_id: str) -> None:
		path = self._path(snapshot_id)
		if not path.is_file():
			raise SnapshotNotFoundError(snapshot_id)
		path.unlink()

	def identifier(self, snapshot_id: str) -> str:
		return self._path(snapshot_id).name

	def _path(self, snapshot_id: str) -> Path:
		if not snapshot_id or any(character not in "0123456789abcdef-" for character in snapshot_id.lower()):
			raise ValueError("snapshot_id contains unsupported characters")
		return self.root / f"{snapshot_id}.json"


def _validate_for_save(snapshot: SchemaSnapshot, *, require_complete: bool) -> None:
	validate_snapshot_integrity(snapshot)
	if require_complete and snapshot.completeness != "complete":
		raise IncompleteSnapshotError("incomplete snapshots cannot be saved as successful baselines")
