"""LangGraph checkpoint saver backed by the site's MariaDB.

LangGraph ships no official MariaDB/MySQL saver, so this mirrors the layout of its
reference InMemorySaver: one row per checkpoint, one row per channel value version
(blob), and one row per pending write. Values are serialised with LangGraph's own
serde and stored base64-encoded, so paused runs survive restarts and are included in
normal site backups.

LangGraph calls put()/put_writes() from an executor thread, but a Frappe job has one
database connection that must only be used from its own thread. So those methods
just serialise and queue their rows; flush() writes them on the job's thread. Reads
flush first, and the runtime flushes after every step. The saver never commits; the
runtime commits after every step.
"""

from __future__ import annotations

import base64
import random
import threading
from collections.abc import Iterator, Sequence
from typing import Any

import frappe
from langgraph.checkpoint.base import (
	WRITES_IDX_MAP,
	BaseCheckpointSaver,
	ChannelVersions,
	Checkpoint,
	CheckpointMetadata,
	CheckpointTuple,
	get_checkpoint_id,
	get_checkpoint_metadata,
	writes_sort_key,
)

CHECKPOINT = "Agent Checkpoint"
BLOB = "Agent Checkpoint Blob"
WRITE = "Agent Checkpoint Write"


def _encode(typed: tuple[str, bytes]) -> tuple[str, str]:
	return typed[0], base64.b64encode(typed[1]).decode()


def _decode(type_: str, data: str | None) -> tuple[str, bytes]:
	return type_, base64.b64decode(data or "")


def _insert(doctype: str, values: dict) -> None:
	doc = frappe.new_doc(doctype)
	doc.update(values)
	doc.name = frappe.generate_hash(length=20)
	doc.db_insert()


class MariaDBSaver(BaseCheckpointSaver[str]):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._lock = threading.Lock()
		self._queue: list = []

	def _defer(self, operation) -> None:
		with self._lock:
			self._queue.append(operation)

	def flush(self) -> None:
		"""Write queued rows. Call only from the thread that owns the database connection."""
		while True:
			with self._lock:
				if not self._queue:
					return
				operations, self._queue = self._queue, []
			for operation in operations:
				operation()

	def _config(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str | None) -> dict | None:
		if not checkpoint_id:
			return None
		return {
			"configurable": {
				"thread_id": thread_id,
				"checkpoint_ns": checkpoint_ns,
				"checkpoint_id": checkpoint_id,
			}
		}

	def _load_blobs(self, thread_id: str, checkpoint_ns: str, versions: ChannelVersions) -> dict[str, Any]:
		if not versions:
			return {}
		rows = frappe.get_all(
			BLOB,
			filters={
				"thread_id": thread_id,
				"checkpoint_ns": checkpoint_ns,
				"channel": ["in", list(versions)],
			},
			fields=["channel", "version", "value_type", "value_data"],
		)
		values = {}
		for row in rows:
			if str(versions.get(row.channel)) != row.version or row.value_type == "empty":
				continue
			values[row.channel] = self.serde.loads_typed(_decode(row.value_type, row.value_data))
		return values

	def _pending_writes(
		self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
	) -> list[tuple[str, str, Any]]:
		rows = frappe.get_all(
			WRITE,
			filters={"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
			fields=["task_id", "task_path", "write_idx", "channel", "value_type", "value_data"],
		)
		rows.sort(key=lambda r: writes_sort_key(r.task_path or "", r.task_id, r.write_idx))
		return [
			(r.task_id, r.channel, self.serde.loads_typed(_decode(r.value_type, r.value_data))) for r in rows
		]

	def _tuple(self, row) -> CheckpointTuple:
		checkpoint: Checkpoint = self.serde.loads_typed(_decode(row.checkpoint_type, row.checkpoint_data))
		return CheckpointTuple(
			config=self._config(row.thread_id, row.checkpoint_ns, row.checkpoint_id),
			checkpoint={
				**checkpoint,
				"channel_values": self._load_blobs(
					row.thread_id, row.checkpoint_ns, checkpoint["channel_versions"]
				),
			},
			metadata=self.serde.loads_typed(_decode(row.metadata_type, row.metadata_data)),
			parent_config=self._config(row.thread_id, row.checkpoint_ns, row.parent_checkpoint_id),
			pending_writes=self._pending_writes(row.thread_id, row.checkpoint_ns, row.checkpoint_id),
		)

	def _rows(self, filters: dict, limit: int | None = None) -> list:
		return frappe.get_all(
			CHECKPOINT,
			filters=filters,
			fields=[
				"thread_id",
				"checkpoint_ns",
				"checkpoint_id",
				"parent_checkpoint_id",
				"checkpoint_type",
				"checkpoint_data",
				"metadata_type",
				"metadata_data",
			],
			order_by="checkpoint_id desc",
			limit=limit,
		)

	def get_tuple(self, config: dict) -> CheckpointTuple | None:
		self.flush()
		configurable = config["configurable"]
		filters = {
			"thread_id": configurable["thread_id"],
			"checkpoint_ns": configurable.get("checkpoint_ns", ""),
		}
		if checkpoint_id := get_checkpoint_id(config):
			filters["checkpoint_id"] = checkpoint_id
		rows = self._rows(filters, limit=1)
		return self._tuple(rows[0]) if rows else None

	def list(
		self,
		config: dict | None,
		*,
		filter: dict[str, Any] | None = None,
		before: dict | None = None,
		limit: int | None = None,
	) -> Iterator[CheckpointTuple]:
		self.flush()
		filters: dict = {}
		if config:
			filters["thread_id"] = config["configurable"]["thread_id"]
			if (ns := config["configurable"].get("checkpoint_ns")) is not None:
				filters["checkpoint_ns"] = ns
			if checkpoint_id := get_checkpoint_id(config):
				filters["checkpoint_id"] = checkpoint_id
		if before and (before_id := get_checkpoint_id(before)):
			filters["checkpoint_id"] = ["<", before_id]
		yielded = 0
		for row in self._rows(filters):
			item = self._tuple(row)
			if filter and not all(item.metadata.get(k) == v for k, v in filter.items()):
				continue
			yield item
			yielded += 1
			if limit is not None and yielded >= limit:
				return

	def put(
		self,
		config: dict,
		checkpoint: Checkpoint,
		metadata: CheckpointMetadata,
		new_versions: ChannelVersions,
	) -> dict:
		thread_id = config["configurable"]["thread_id"]
		checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
		copy = checkpoint.copy()
		values: dict[str, Any] = copy.pop("channel_values")
		rows: list[tuple[str, dict]] = []
		for channel, version in new_versions.items():
			typed = self.serde.dumps_typed(values[channel]) if channel in values else ("empty", b"")
			value_type, value_data = _encode(typed)
			rows.append(
				(
					BLOB,
					{
						"thread_id": thread_id,
						"checkpoint_ns": checkpoint_ns,
						"channel": channel,
						"version": str(version),
						"value_type": value_type,
						"value_data": value_data,
					},
				)
			)
		checkpoint_type, checkpoint_data = _encode(self.serde.dumps_typed(copy))
		metadata_type, metadata_data = _encode(
			self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
		)
		rows.append(
			(
				CHECKPOINT,
				{
					"thread_id": thread_id,
					"checkpoint_ns": checkpoint_ns,
					"checkpoint_id": checkpoint["id"],
					"parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
					"checkpoint_type": checkpoint_type,
					"checkpoint_data": checkpoint_data,
					"metadata_type": metadata_type,
					"metadata_data": metadata_data,
				},
			)
		)
		self._defer(lambda: [_insert(doctype, row) for doctype, row in rows])
		return self._config(thread_id, checkpoint_ns, checkpoint["id"])

	def put_writes(
		self, config: dict, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = ""
	) -> None:
		thread_id = config["configurable"]["thread_id"]
		checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
		checkpoint_id = config["configurable"]["checkpoint_id"]
		key = {
			"thread_id": thread_id,
			"checkpoint_ns": checkpoint_ns,
			"checkpoint_id": checkpoint_id,
			"task_id": task_id,
		}
		rows = []
		for idx, (channel, value) in enumerate(writes):
			value_type, value_data = _encode(self.serde.dumps_typed(value))
			rows.append(
				{
					**key,
					"task_path": task_path,
					"write_idx": WRITES_IDX_MAP.get(channel, idx),
					"channel": channel,
					"value_type": value_type,
					"value_data": value_data,
				}
			)

		def store():
			for row in rows:
				existing = frappe.get_all(WRITE, filters={**key, "write_idx": row["write_idx"]}, pluck="name")
				if existing:
					# Regular writes are immutable; special writes (errors, interrupts) are replaced.
					if row["write_idx"] >= 0:
						continue
					frappe.db.delete(WRITE, {"name": ["in", existing]})
				_insert(WRITE, row)

		self._defer(store)

	def delete_thread(self, thread_id: str) -> None:
		self.flush()
		for doctype in (CHECKPOINT, BLOB, WRITE):
			frappe.db.delete(doctype, {"thread_id": thread_id})

	def get_next_version(self, current: str | None, channel: None = None) -> str:
		if current is None:
			current_v = 0
		elif isinstance(current, int):
			current_v = current
		else:
			current_v = int(current.split(".")[0])
		return f"{current_v + 1:032}.{random.random():016}"
