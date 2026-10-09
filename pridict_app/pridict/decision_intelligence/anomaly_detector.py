"""Statistical and pattern-based anomaly detection for procurement transactions."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import quote

from pridict.decision_intelligence.models import AnomalyFinding, AnomalySeverity


def detect_price_variances(
	po_rows: list[dict[str, Any]],
	po_items: list[dict[str, Any]],
	historical_item_rates: dict[str, float] | None = None,
) -> list[AnomalyFinding]:
	"""Detects item line unit rates that significantly exceed historical or benchmark rates."""
	anomalies: list[AnomalyFinding] = []
	benchmarks = historical_item_rates or {}

	# If no external benchmarks provided, build item median rates from the current dataset
	if not benchmarks:
		item_rates: dict[str, list[float]] = defaultdict(list)
		for item in po_items:
			item_code = str(item.get("item_code") or "").strip()
			rate = float(item.get("rate") or 0.0)
			if item_code and rate > 0:
				item_rates[item_code].append(rate)
		for code, rates in item_rates.items():
			sorted_rates = sorted(rates)
			mid = len(sorted_rates) // 2
			benchmarks[code] = sorted_rates[mid]

	# Check each item row against benchmark
	po_map = {row["name"]: row for row in po_rows if "name" in row}
	for item in po_items:
		item_code = str(item.get("item_code") or "").strip()
		rate = float(item.get("rate") or 0.0)
		qty = float(item.get("qty") or 0.0)
		parent_po = str(item.get("parent") or "")
		benchmark = benchmarks.get(item_code, 0.0)

		if benchmark > 0 and rate > benchmark and qty > 0:
			pct_variance = ((rate - benchmark) / benchmark) * 100.0
			if pct_variance >= 10.0:  # 10% or more above benchmark
				impact = (rate - benchmark) * qty
				severity = AnomalySeverity.HIGH if pct_variance >= 25.0 or impact > 50000.0 else AnomalySeverity.MEDIUM
				po_doc = po_map.get(parent_po, {})
				supplier = po_doc.get("supplier") or ""
				doc_url = f"/app/purchase-order/{quote(parent_po, safe='')}"

				anomalies.append(
					AnomalyFinding(
						anomaly_id=f"ANOM-PRICE-{parent_po}-{item.get('name') or item_code}",
						anomaly_type="PRICE_VARIANCE_OUTLIER",
						severity=severity,
						title=f"Price Outlier: {item_code} (+{pct_variance:.1f}%)",
						description=(
							f"Unit price {rate:,.2f} on {parent_po} is {pct_variance:.1f}% higher than "
							f"the benchmark {benchmark:,.2f} for {item_code}. "
							f"Estimated cost impact: {impact:,.2f}."
						),
						doc_type="Purchase Order",
						doc_name=parent_po,
						party_name=supplier,
						item_code=item_code,
						amount=rate * qty,
						variance_percent=pct_variance,
						potential_impact=impact,
						doc_url=doc_url,
					)
				)

	return anomalies


def detect_split_purchases(po_rows: list[dict[str, Any]]) -> list[AnomalyFinding]:
	"""Detects potential split purchase orders issued to the same supplier within 48 hours

	aimed at staying under individual approval thresholds.
	"""
	anomalies: list[AnomalyFinding] = []
	supplier_pos: dict[str, list[dict[str, Any]]] = defaultdict(list)

	for po in po_rows:
		supplier = str(po.get("supplier") or "").strip()
		if supplier and float(po.get("grand_total") or 0.0) > 0:
			supplier_pos[supplier].append(po)

	threshold_single = 150000.0  # L3 approval boundary

	for supplier, orders in supplier_pos.items():
		if len(orders) < 2:
			continue

		# Sort by transaction / creation date
		sorted_orders = sorted(
			orders,
			key=lambda x: str(x.get("transaction_date") or x.get("creation") or ""),
		)

		for i in range(len(sorted_orders)):
			for j in range(i + 1, len(sorted_orders)):
				po1 = sorted_orders[i]
				po2 = sorted_orders[j]
				d1_str = str(po1.get("transaction_date") or po1.get("creation") or "")[:10]
				d2_str = str(po2.get("transaction_date") or po2.get("creation") or "")[:10]

				try:
					d1 = datetime.strptime(d1_str, "%Y-%m-%d")
					d2 = datetime.strptime(d2_str, "%Y-%m-%d")
					day_diff = abs((d2 - d1).days)
				except Exception:
					day_diff = 999

				amt1 = float(po1.get("grand_total") or 0.0)
				amt2 = float(po2.get("grand_total") or 0.0)
				combined = amt1 + amt2

				# If individually each is <= 150,000 but combined > 150,000 within 2 days
				if day_diff <= 2 and amt1 <= threshold_single and amt2 <= threshold_single and combined > threshold_single:
					anomalies.append(
						AnomalyFinding(
							anomaly_id=f"ANOM-SPLIT-{po1['name']}-{po2['name']}",
							anomaly_type="SPLIT_PURCHASE_CIRCUMVENTION",
							severity=AnomalySeverity.HIGH,
							title=f"Potential Split Purchase: {po1['name']} & {po2['name']}",
							description=(
								f"Two purchase orders to {supplier} ({amt1:,.2f} on {d1_str} and {amt2:,.2f} on {d2_str}) "
								f"aggregate to {combined:,.2f}, circumventing the {threshold_single:,.2f} single-order approval tier."
							),
							doc_type="Purchase Order",
							doc_name=f"{po1['name']}, {po2['name']}",
							party_name=supplier,
							amount=combined,
							variance_percent=0.0,
							potential_impact=combined,
							doc_url=f"/app/purchase-order/{quote(po1['name'], safe='')}",
						)
					)

	return anomalies


def detect_maverick_orders(
	po_rows: list[dict[str, Any]],
	po_items: list[dict[str, Any]],
) -> list[AnomalyFinding]:
	"""Detects high-value Purchase Orders that bypassed standard requisition and RFQ flows."""
	anomalies: list[AnomalyFinding] = []
	items_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for item in po_items:
		items_by_parent[str(item.get("parent") or "")].append(item)

	for po in po_rows:
		name = str(po.get("name") or "")
		amount = float(po.get("grand_total") or 0.0)
		items = items_by_parent.get(name, [])
		supplier = str(po.get("supplier") or "")

		# Check for sourcing links
		has_sourcing = any(
			bool(i.get("material_request") or i.get("supplier_quotation"))
			for i in items
		)

		if not has_sourcing and amount > 50000.0:
			severity = AnomalySeverity.HIGH if amount > 200000.0 else AnomalySeverity.MEDIUM
			anomalies.append(
				AnomalyFinding(
					anomaly_id=f"ANOM-MAVERICK-{name}",
					anomaly_type="MAVERICK_UNLINKED_SPEND",
					severity=severity,
					title=f"Unlinked Maverick Spend on {name}",
					description=(
						f"Purchase Order {name} for {amount:,.2f} to {supplier} was raised directly "
						f"without an upstream approved Material Request or competitive Supplier Quotation."
					),
					doc_type="Purchase Order",
					doc_name=name,
					party_name=supplier,
					amount=amount,
					potential_impact=amount * 0.10,  # 10% estimated maverick spend premium
					doc_url=f"/app/purchase-order/{quote(name, safe='')}",
				)
			)

	return anomalies
