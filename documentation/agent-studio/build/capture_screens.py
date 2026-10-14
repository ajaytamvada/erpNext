"""Capture Agent Studio preview screenshots with headless Chrome.

Usage: python capture_screens.py [chrome_path]
Writes PNGs to ../images/. Each page is rendered in a tall window, then the
empty background below the content is trimmed.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
PREVIEW = (HERE.parent / "preview" / "preview.html").as_uri()
OUT = HERE.parent / "images"
CHROME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WIDTH = 1280
BACKGROUND = (247, 248, 250)

SHOTS = [
	("01-models", "agent-models", "", 1900),
	("02-agents", "agent-registry", "", 2200),
	("03-workflow", "agent-workflows", "", 2000),
	("04-tools", "agent-tools", "", 1500),
	("05-policies", "agent-policies", "", 2000),
	("06-runs", "agent-runs", "", 1900),
	("06b-evals", "agent-runs", ".as-tab[data-tab=evals]", 1700),
	("07-approvals", "agent-approvals", "", 2000),
]


def trim(path: Path) -> None:
	image = Image.open(path).convert("RGB")
	diff = ImageChops.difference(image, Image.new("RGB", image.size, BACKGROUND))
	box = diff.getbbox()
	if box:
		image.crop((0, 0, image.width, min(image.height, box[3] + 24))).save(path)


def main() -> None:
	OUT.mkdir(exist_ok=True)
	for name, page, click, height in SHOTS:
		target = OUT / f"{name}.png"
		url = f"{PREVIEW}?page={page}" + (f"&click={click}" if click else "")
		subprocess.run(
			[
				CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
				"--force-device-scale-factor=2", f"--window-size={WIDTH},{height}", "--virtual-time-budget=4000",
				f"--screenshot={target}", url,
			],
			check=True,
			capture_output=True,
		)
		trim(target)
		print(f"{target.name}: {Image.open(target).size}")


if __name__ == "__main__":
	main()
