"""Capture Agent Studio screenshots from a running site with Playwright.

Usage: python capture_screens.py [base_url] [user] [password]
Defaults: http://development.localhost:8008 Administrator admin
Requires: pip install playwright pillow (uses the installed Chrome, no browser download).
Writes PNGs to ../images/, trimmed to the page content.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://development.localhost:8008"
USER = sys.argv[2] if len(sys.argv) > 2 else "Administrator"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "admin"
WIDTH = 1400

# (file name, route, element to click first or "")
SHOTS = [
	("01-models", "agent-models", ""),
	("02-agents", "agent-registry", ""),
	("03-workflow", "agent-workflows", ""),
	("04-tools", "agent-tools", ""),
	("05-policies", "agent-policies", ""),
	("06-runs", "agent-runs", ""),
	("06b-evals", "agent-runs", ".as-tab[data-tab=evals]"),
	("07-approvals", "agent-approvals", ""),
]


def trim(path: Path) -> None:
	"""Cut the empty background below the content."""
	image = Image.open(path).convert("RGB")
	background = image.getpixel((image.width - 5, image.height - 5))
	box = ImageChops.difference(image, Image.new("RGB", image.size, background)).getbbox()
	if box:
		image.crop((0, 0, image.width, min(image.height, box[3] + 24))).save(path)


def main() -> None:
	OUT.mkdir(exist_ok=True)
	host = urlparse(BASE).hostname
	args = [f"--host-resolver-rules=MAP {host} 127.0.0.1"] if host and host.endswith(".localhost") else []
	with sync_playwright() as p:
		browser = p.chromium.launch(channel="chrome", args=args)
		page = browser.new_page(viewport={"width": WIDTH, "height": 1000}, device_scale_factor=2)
		page.goto(f"{BASE}/login")
		page.evaluate(
			"([usr, pwd]) => fetch('/api/method/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({usr, pwd})})",
			[USER, PASSWORD],
		)
		for name, route, click in SHOTS:
			page.goto(f"{BASE}/app/{route}")
			page.wait_for_load_state("networkidle")
			# Desk's sticky bars would otherwise overlap the top of the captured area.
			page.add_style_tag(content=".navbar, .page-head { display: none !important; }")
			if click:
				page.click(click)
			page.wait_for_timeout(1200)
			target = OUT / f"{name}.png"
			page.locator(".as-screen").screenshot(path=str(target))
			trim(target)
			print(f"{target.name}: {Image.open(target).size}")
		browser.close()


if __name__ == "__main__":
	main()
