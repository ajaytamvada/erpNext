from __future__ import annotations

import json
from pathlib import Path

import frappe

from pridict.schema_intelligence.models import SchemaSnapshot
from pridict.schema_intelligence.service import (
	capture_snapshot,
	get_default_repository as get_schema_repository,
)

from pridict.process_intelligence.collection import (
	ConfigurationSource,
	FrappeConfigurationSource,
	collect_purchasing_configuration,
)
from pridict.process_intelligence.graph import build_process_graph
from pridict.process_intelligence.modeling import build_purchasing_process_model
from pridict.process_intelligence.models import ProcessModel
from pridict.process_intelligence.persistence import FilesystemProcessModelRepository, ProcessModelRepository
from pridict.process_intelligence.reporting import render_process_report
from pridict.process_intelligence.reconstruction import reconstruct_purchasing
from pridict.process_intelligence.reconstruction_graph import build_reconstruction_graph
from pridict.process_intelligence.reconstruction_persistence import FilesystemReconstructionRepository
from pridict.process_intelligence.reconstruction_reporting import render_reconstruction_report
from pridict.process_intelligence.schema_adapter import SchemaSnapshotAdapter
from pridict.process_intelligence.transaction_collection import (
	FrappeTransactionSource,
	TransactionSource,
	collect_transactions,
)
from pridict.process_intelligence.transaction_models import ReconstructionResult, TransactionScope


def analyze_purchasing(
	*,
	snapshot: SchemaSnapshot | None = None,
	snapshot_id: str | None = None,
	source: ConfigurationSource | None = None,
) -> ProcessModel:
	if snapshot is not None and snapshot_id is not None:
		raise ValueError("provide snapshot or snapshot_id, not both")
	if snapshot_id:
		snapshot = get_schema_repository().load(snapshot_id)
	if snapshot is None:
		snapshot = capture_snapshot()
	schema = SchemaSnapshotAdapter().adapt_purchasing(snapshot)
	configuration = collect_purchasing_configuration(schema, source or FrappeConfigurationSource())
	return build_purchasing_process_model(schema, configuration)


def analyze_and_persist_purchasing(
	*,
	snapshot: SchemaSnapshot | None = None,
	snapshot_id: str | None = None,
	source: ConfigurationSource | None = None,
	repository: ProcessModelRepository | None = None,
) -> ProcessModel:
	model = analyze_purchasing(snapshot=snapshot, snapshot_id=snapshot_id, source=source)
	(repository or get_default_repository()).save(model)
	return model


def process_artifacts(model: ProcessModel) -> dict:
	return {
		"model": model.to_dict(),
		"graph": build_process_graph(model),
		"report": render_process_report(model),
	}


def write_process_artifacts(model: ProcessModel, directory: str | Path) -> dict[str, str]:
	target = Path(directory)
	target.mkdir(parents=True, exist_ok=True)
	artifacts = process_artifacts(model)
	paths = {
		"model": target / "purchasing-process-model.json",
		"graph": target / "purchasing-process-graph.json",
		"report": target / "purchasing-process-report.txt",
	}
	for key in ("model", "graph"):
		paths[key].write_text(
			json.dumps(artifacts[key], ensure_ascii=False, sort_keys=True, indent=2) + "\n",
			encoding="utf-8",
		)
	paths["report"].write_text(artifacts["report"], encoding="utf-8")
	return {key: str(path) for key, path in paths.items()}


def get_default_repository() -> FilesystemProcessModelRepository:
	root = Path(frappe.get_site_path("private", "files", "pridict-process-intelligence"))
	return FilesystemProcessModelRepository(root)


def reconstruct_purchasing_transactions(
	scope: TransactionScope,
	*,
	snapshot: SchemaSnapshot | None = None,
	configuration_source: ConfigurationSource | None = None,
	transaction_source: TransactionSource | None = None,
) -> ReconstructionResult:
	snapshot = snapshot or capture_snapshot()
	schema = SchemaSnapshotAdapter().adapt_purchasing(snapshot)
	configuration = collect_purchasing_configuration(
		schema,
		configuration_source or FrappeConfigurationSource(),
	)
	process_model = build_purchasing_process_model(schema, configuration)
	dataset = collect_transactions(schema, scope, transaction_source or FrappeTransactionSource())
	return reconstruct_purchasing(process_model, schema, scope, dataset)


def reconstruction_artifacts(result: ReconstructionResult) -> dict:
	return {
		"reconstruction": result.to_dict(),
		"graph": build_reconstruction_graph(result),
		"report": render_reconstruction_report(result),
	}


def get_reconstruction_repository() -> FilesystemReconstructionRepository:
	root = Path(frappe.get_site_path("private", "files", "pridict-process-reconstruction"))
	return FilesystemReconstructionRepository(root)


def reconstruct_and_persist_purchasing(scope: TransactionScope) -> ReconstructionResult:
	result = reconstruct_purchasing_transactions(scope)
	get_reconstruction_repository().save(result)
	return result


def write_reconstruction_artifacts(result: ReconstructionResult, directory: str | Path) -> dict[str, str]:
	target = Path(directory)
	target.mkdir(parents=True, exist_ok=True)
	artifacts = reconstruction_artifacts(result)
	paths = {
		"reconstruction": target / "purchasing-actual-reconstruction.json",
		"graph": target / "purchasing-actual-graph.json",
		"report": target / "purchasing-actual-report.txt",
	}
	for key in ("reconstruction", "graph"):
		paths[key].write_text(
			json.dumps(artifacts[key], ensure_ascii=False, sort_keys=True, indent=2) + "\n",
			encoding="utf-8",
		)
	paths["report"].write_text(artifacts["report"], encoding="utf-8")
	return {key: str(path) for key, path in paths.items()}


def generate_purchasing_reconstruction_artifacts(
	company: str,
	start_date: str,
	end_date: str,
	directory: str,
	max_records_per_doctype: int = 5000,
) -> dict[str, str]:
	"""Generate review artifacts from a bounded, read-only transaction extraction."""
	scope = TransactionScope(company, start_date, end_date, int(max_records_per_doctype))
	result = reconstruct_purchasing_transactions(scope)
	return write_reconstruction_artifacts(result, directory)
