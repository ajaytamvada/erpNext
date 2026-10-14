"""Build Agent-Studio-Explainer.pdf from the HTML source with headless Chrome.

Usage:
	python build_pdf.py              # diagrams + PDF (uses existing screenshots)
	python build_pdf.py --screens [base_url user password]
	                                 # also recapture screenshots from a running site first
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main() -> None:
	subprocess.run([sys.executable, str(HERE / "diagrams.py")], check=True)
	if "--screens" in sys.argv:
		extra = [a for a in sys.argv[1:] if a != "--screens"]
		subprocess.run([sys.executable, str(HERE / "capture_screens.py"), *extra], check=True)
	source = (DOCS / "Agent-Studio-Explainer.html").as_uri()
	target = DOCS / "Agent-Studio-Explainer.pdf"
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
