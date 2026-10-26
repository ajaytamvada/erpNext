"""Build Automation-Builder-Explainer.pdf from the HTML source with headless Chrome.

Usage: python build_pdf.py
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main() -> None:
	source = (DOCS / "Automation-Builder-Explainer.html").as_uri()
	target = DOCS / "Automation-Builder-Explainer.pdf"
	subprocess.run(
		[
			CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
			"--no-pdf-header-footer", "--virtual-time-budget=5000",
			f"--print-to-pdf={target}", source,
		],
		check=True,
		capture_output=True,
	)
	print(f"PDF written: {target} ({target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
	main()
