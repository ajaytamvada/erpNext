"""HTTP integration checks against the local test site; not a browser or visual test."""
import json
import re
from pathlib import Path
import time

import requests


BASE = "http://127.0.0.1:8000"
HOST = "process-intelligence.localhost"
OUTPUT = Path("/workspace/development/apps/erpnext/documentation/process-intelligence/evidence")
METHOD = "/api/method/pridict.process_intelligence.purchasing_screen."


def session(user=None):
	s = requests.Session()
	s.headers["Host"] = HOST
	if user:
		r = s.post(BASE + "/api/method/login", data={"usr": user, "pwd": "Local-PI-Demo-2026!"}, timeout=30)
		r.raise_for_status()
	return s


def main():
	results = {}
	guest = session()
	results["login_http"] = guest.get(BASE + "/login", timeout=30).status_code
	assert results["login_http"] == 200
	assert guest.get(BASE + METHOD + "get_options", timeout=30).status_code == 403
	results["guest_api_denied"] = True
	user = session("pi.analyst@example.test")
	desk = user.get(BASE + "/app/process-intelligence", timeout=30)
	desk.raise_for_status()
	token = re.search(r'frappe.csrf_token = "([^"]+)"', desk.text)
	assert token, "Desk did not return a CSRF token"
	user.headers["X-Frappe-CSRF-Token"] = token.group(1)
	page = user.get(BASE + "/api/method/frappe.desk.desk_page.getpage", params={"name": "process-intelligence"}, timeout=30)
	page.raise_for_status()
	assert "PurchasingProcessIntelligence" in page.text, page.text[:400]
	assert "purchasing_screen.get_analysis" in page.text
	results["authorized_page_script"] = True
	for asset in ("/assets/pridict/css/process_intelligence.css", "/assets/pridict/js/ui/shell.js"):
		r = user.get(BASE + asset, timeout=30)
		r.raise_for_status()
		assert ("pi-screen" if asset.endswith(".css") else 'route: "process-intelligence"') in r.text
	results["page_css_and_navigation_asset"] = True
	options = user.get(BASE + METHOD + "get_options", timeout=30).json()["message"]
	assert options["companies"] == ["PI Demonstration"]
	start = time.monotonic()
	r = user.post(BASE + METHOD + "get_analysis", data={"company": "PI Demonstration", "start_date": "2026-10-02", "end_date": "2026-10-02"}, timeout=180)
	r.raise_for_status()
	data = r.json()["message"]
	assert len(data["documents"]) == 7
	assert len(data["reconstruction"]["instances"]) == 1
	assert len(data["reconstruction"]["edges"]) == 10
	results["analysis_seconds"] = round(time.monotonic() - start, 2)
	results["ordinary_analyst_analysis"] = {"documents": 7, "journeys": 1, "links": 10}
	for doc in data["documents"].values():
		r = user.get(BASE + "/api/method/frappe.desk.form.load.getdoc", params={"doctype": doc["doctype"], "name": doc["name"]}, timeout=30)
		r.raise_for_status()
		assert any(item.get("name") == doc["name"] for item in r.json().get("docs", []))
	results["supporting_documents_load"] = 7
	denied = session("pi.noaccess@example.test")
	assert denied.get(BASE + METHOD + "get_options", timeout=30).status_code == 403
	r = denied.get(BASE + "/api/method/frappe.desk.desk_page.getpage", params={"name": "process-intelligence"}, timeout=30)
	assert r.status_code == 403, r.text[:400]
	results["user_without_analysis_role_page_and_api_denied"] = True
	r = user.post(BASE + METHOD + "get_analysis", data={"company": "PI Empty Company", "start_date": "2026-10-02", "end_date": "2026-10-02"}, timeout=30)
	assert r.status_code == 403
	results["other_company_api_denied"] = True
	OUTPUT.mkdir(parents=True, exist_ok=True)
	(OUTPUT / "http-verification.json").write_text(json.dumps(results, indent=2) + "\n")
	print(json.dumps(results, indent=2))


if __name__ == "__main__":
	main()
