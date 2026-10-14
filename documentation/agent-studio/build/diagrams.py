"""Generate the SVG diagrams used in the Agent Studio explainer PDF.

Usage: python diagrams.py   -> writes ../images/workflow.svg and ../images/architecture.svg
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "images"

KIND_STYLE = {
	"llm": ("#f3edff", "#8b5cf6"),
	"tool": ("#eaf1ff", "#3b82f6"),
	"rule": ("#f1f4f7", "#64748b"),
	"router": ("#fff7db", "#d4a106"),
	"human": ("#fff0e5", "#f97316"),
	"end": ("#e8f8ee", "#22a35a"),
}
FONT = "Segoe UI, Inter, Arial, sans-serif"


def workflow_svg() -> str:
	cols = {"L": 115, "C": 385, "R": 655}
	widths = {"L": 190, "C": 240, "R": 190}
	h, step, top = 36, 58, 14
	nodes = {
		"start": ("C", 0, "START: buyer request", "end"),
		"parse": ("C", 1, "1 · Parse requirement", "llm"),
		"resolve": ("C", 2, "2 · Resolve ERPNext records", "tool"),
		"validate": ("C", 3, "3 · Validate inputs & permissions", "rule"),
		"read": ("C", 4, "4 · Read stock & open supply", "tool"),
		"ask": ("R", 4.5, "Ask buyer (pause)", "human"),
		"calc": ("C", 5, "5 · Calculate net shortage", "rule"),
		"router": ("C", 6, "6 · Shortage exists?", "router"),
		"explain": ("L", 6, "Explain: no purchase", "llm"),
		"end1": ("L", 7, "END", "end"),
		"find": ("C", 7, "7 · Find eligible suppliers", "tool"),
		"analyze": ("C", 8, "8 · Analyze sourcing options", "llm"),
		"prepare": ("C", 9, "9 · Prepare recommendation", "llm"),
		"review": ("C", 10, "10 · Human review (pause)", "human"),
		"reject": ("L", 10, "Record rejection", "rule"),
		"end2": ("L", 11, "END", "end"),
		"revalidate": ("C", 11, "11 · Re-validate policies", "rule"),
		"create": ("C", 12, "12 · Create DRAFT RFQ", "tool"),
		"verify": ("C", 13, "13 · Verify & audit", "rule"),
		"end3": ("C", 14, "END", "end"),
	}

	def box(key):
		col, row, _, _ = nodes[key]
		w = widths[col]
		x = cols[col] - w / 2
		y = top + row * step
		return x, y, w, h

	parts = []
	for key, (col, row, label, kind) in nodes.items():
		x, y, w, hh = box(key)
		fill, stroke = KIND_STYLE[kind]
		if kind == "router":
			cx, cy = x + w / 2, y + hh / 2
			pts = f"{cx},{cy - 22} {cx + w / 2},{cy} {cx},{cy + 22} {cx - w / 2},{cy}"
			parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
		else:
			rx = 18 if kind == "end" else 8
			parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
		parts.append(f'<text x="{x + w / 2}" y="{y + hh / 2 + 4.5}" text-anchor="middle" font-size="12.5" font-weight="600" fill="#1f272e">{escape(label)}</text>')

	def anchor(key, side):
		x, y, w, hh = box(key)
		return {"top": (x + w / 2, y), "bottom": (x + w / 2, y + hh), "left": (x, y + hh / 2), "right": (x + w, y + hh / 2)}[side]

	def edge(points, label="", label_at=None, color="#8a94a3"):
		d = " ".join(f"{'M' if i == 0 else 'L'}{px},{py}" for i, (px, py) in enumerate(points))
		parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.5" marker-end="url(#arrow)"/>')
		if label:
			lx, ly = label_at
			parts.append(f'<text x="{lx}" y="{ly}" font-size="11" font-weight="700" fill="#4b5563" text-anchor="middle" paint-order="stroke" stroke="#ffffff" stroke-width="4">{escape(label)}</text>')

	spine = ["start", "parse", "resolve", "validate", "read", "calc", "router", "find", "analyze", "prepare", "review", "revalidate", "create", "verify", "end3"]
	labels = {("router", "find"): "yes", ("validate", "read"): "valid", ("find", "analyze"): "enough data", ("review", "revalidate"): "approved", ("revalidate", "create"): "pass"}
	for a, b in zip(spine, spine[1:]):
		p1 = anchor(a, "bottom")
		p2 = anchor(b, "top")
		if a == "router":
			p1 = (p1[0], p1[1] + 4)
		lab = labels.get((a, b), "")
		edge([p1, p2], lab, (p1[0] + 34, (p1[1] + p2[1]) / 2 + 4) if lab else None)

	# Branches
	vx, vy = anchor("validate", "right")
	ax, ay = anchor("ask", "top")
	edge([(vx, vy), (ax, vy), (ax, ay)], "missing data", (ax - 20, vy - 6))
	fx, fy = anchor("find", "right")
	bx, by = anchor("ask", "bottom")
	edge([(fx, fy), (bx, fy), (bx, by)], "not enough", (bx - 4, fy - 6))
	rx_, ry_ = anchor("ask", "right")
	resx, resy = anchor("resolve", "right")
	edge([(rx_, ry_), (rx_ + 22, ry_), (rx_ + 22, resy), (resx, resy)], "answered", (rx_ - 14, resy - 6))
	rtx, rty = anchor("router", "left")
	ex, ey = anchor("explain", "right")
	edge([(rtx + 2, rty), (ex, ey)], "no", ((rtx + ex) / 2, rty - 6))
	edge([anchor("explain", "bottom"), anchor("end1", "top")])
	rvx, rvy = anchor("review", "left")
	rjx, rjy = anchor("reject", "right")
	edge([(rvx, rvy), (rjx, rjy)], "rejected", ((rvx + rjx) / 2, rvy - 6))
	edge([anchor("reject", "bottom"), anchor("end2", "top")])
	fvx, fvy = anchor("revalidate", "right")
	rvrx, rvry = anchor("review", "right")
	edge([(fvx, fvy), (fvx + 30, fvy), (fvx + 30, rvry), (rvrx, rvry)], "fail", (fvx + 42, (fvy + rvry) / 2 + 4))

	# Legend
	ly = top + 15 * step + 4
	lx = 20
	for kind, name in [("llm", "LLM step"), ("tool", "Tool call (ERPNext)"), ("rule", "Rule (Python code)"), ("router", "Router"), ("human", "Human pause (interrupt)")]:
		fill, stroke = KIND_STYLE[kind]
		parts.append(f'<rect x="{lx}" y="{ly}" width="16" height="12" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
		parts.append(f'<text x="{lx + 22}" y="{ly + 10.5}" font-size="11.5" fill="#374151">{escape(name)}</text>')
		lx += 150

	height = ly + 24
	return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 {height}" width="780" height="{height}" font-family="{FONT}">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a94a3"/></marker></defs>
{"".join(parts)}
</svg>'''


def architecture_svg() -> str:
	layers = [
		("Agent Studio UI (Frappe Desk pages)", "Models · Agents · Workflows · Tools · Policies · Runs · Approvals", "#eaf1ff", "#3b82f6"),
		("Agent Configuration API (whitelisted Python)", "Validate · version · publish configurations", "#f1f4f7", "#64748b"),
		("LangGraph Runtime (background worker)", "State · routing · checkpoints · human interrupts · step & token limits", "#f3edff", "#8b5cf6"),
	]
	side = [
		("LLM Gateway", "Providers · secrets · retries · fallback · usage limits", "#fff7db", "#d4a106"),
		("Tool Layer", "Read tools · draft-write tools · reuses decision_intelligence", "#eaf1ff", "#3b82f6"),
		("Policy Engine", "Limits · approved suppliers · approval rules", "#fff0e5", "#f97316"),
	]
	parts = []
	y = 10
	for title, sub, fill, stroke in layers:
		parts.append(f'<rect x="20" y="{y}" width="740" height="58" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
		parts.append(f'<text x="390" y="{y + 25}" text-anchor="middle" font-size="15" font-weight="700" fill="#1f272e">{escape(title)}</text>')
		parts.append(f'<text x="390" y="{y + 45}" text-anchor="middle" font-size="12" fill="#4b5563">{escape(sub)}</text>')
		parts.append(f'<path d="M390,{y + 58} L390,{y + 78}" stroke="#8a94a3" stroke-width="1.6" marker-end="url(#arrow)"/>')
		y += 80
	# The runtime also calls the gateway and the policy engine, not just the tools.
	parts.append(f'<path d="M138,{y - 22} L138,{y - 2}" stroke="#8a94a3" stroke-width="1.6" marker-end="url(#arrow)"/>')
	parts.append(f'<path d="M642,{y - 22} L642,{y - 2}" stroke="#8a94a3" stroke-width="1.6" marker-end="url(#arrow)"/>')
	x = 20
	for title, sub, fill, stroke in side:
		parts.append(f'<rect x="{x}" y="{y}" width="236" height="70" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
		parts.append(f'<text x="{x + 118}" y="{y + 28}" text-anchor="middle" font-size="14.5" font-weight="700" fill="#1f272e">{escape(title)}</text>')
		words, line, lines = sub.split(" "), "", []
		for word in words:
			if len(line) + len(word) > 34:
				lines.append(line)
				line = word
			else:
				line = f"{line} {word}".strip()
		lines.append(line)
		for i, text in enumerate(lines):
			parts.append(f'<text x="{x + 118}" y="{y + 47 + i * 14}" text-anchor="middle" font-size="11.5" fill="#4b5563">{escape(text)}</text>')
		x += 252
	box_top = y + 70
	y += 98
	bottom = [
		("LLM providers", "Anthropic · OpenAI · Google · local", "#fff7db", "#d4a106"),
		("ERPNext (MariaDB)", "Items · Stock · POs · RFQs · Agent records", "#e8f8ee", "#22a35a"),
		("Checkpoint store", "Saved state of paused runs", "#f1f4f7", "#64748b"),
	]
	for i, (title, sub, fill, stroke) in enumerate(bottom):
		bx = 20 + i * 252
		parts.append(f'<rect x="{bx}" y="{y}" width="236" height="62" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
		parts.append(f'<text x="{bx + 118}" y="{y + 26}" text-anchor="middle" font-size="14.5" font-weight="700" fill="#1f272e">{escape(title)}</text>')
		parts.append(f'<text x="{bx + 118}" y="{y + 45}" text-anchor="middle" font-size="11" fill="#4b5563">{escape(sub)}</text>')
	arrow = 'stroke="#8a94a3" stroke-width="1.6" fill="none" marker-end="url(#arrow)"'
	parts.append(f'<path d="M138,{box_top} L138,{y}" {arrow}/>')
	parts.append(f'<path d="M390,{box_top} L390,{y}" {arrow}/>')
	parts.append(f'<path d="M642,{box_top} L470,{y}" {arrow}/>')
	runtime_mid = 10 + 2 * 80 + 29
	parts.append(f'<path d="M760,{runtime_mid} L774,{runtime_mid} L774,{y + 31} L760,{y + 31}" {arrow}/>')
	height = y + 72
	return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 {height}" width="780" height="{height}" font-family="{FONT}">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a94a3"/></marker></defs>
{"".join(parts)}
</svg>'''


if __name__ == "__main__":
	OUT.mkdir(exist_ok=True)
	(OUT / "workflow.svg").write_text(workflow_svg(), encoding="utf-8")
	(OUT / "architecture.svg").write_text(architecture_svg(), encoding="utf-8")
	print("diagrams written")
