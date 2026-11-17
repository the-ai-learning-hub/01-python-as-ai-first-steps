"""Static checks for the lesson notebooks (structure, links, leftovers).

    uv run python tools/audit_notebooks.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ["Tech Leaders", "Iscte", "Pós-graduação", "!pip install", "rodar", "na tela", "você", "Vullkano", "<!DOCTYPE", "<style"]


def audit(path: Path) -> list[str]:
    nb = nbformat.read(path, as_version=4)
    problems: list[str] = []
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    for word in FORBIDDEN:
        if word.lower() in (md + code).lower():
            problems.append(f"contains '{word}'")
    if "The AI Learning Hub" not in nb.cells[0].source:
        problems.append("first cell is not the banner")
    if "Licença MIT" not in nb.cells[-1].source:
        problems.append("last cell is not the footer")
    if "colab-badge" not in md:
        problems.append("missing Colab badge")
    anchors = set(re.findall(r'<a id="([^"]+)"></a>', md))
    for target in set(re.findall(r"\]\(#([^)]+)\)", md)):
        if target not in anchors:
            problems.append(f"index link #{target} has no anchor")
    for rel in set(re.findall(r"\]\((\.\.?/[^)#]+)\)", md)):
        if not (path.parent / rel).resolve().exists():
            problems.append(f"broken relative link {rel}")
    if md.count("<details>") != md.count("</details>"):
        problems.append("unbalanced <details>")
    if re.search(r"^\s*[^#\n]*\binput\(", code, re.M):
        problems.append("executed input() call")
    for c in nb.cells:
        if c.cell_type == "code" and c.get("execution_count") is None and c.source.strip():
            problems.append("notebook not executed (cells without outputs)")
            break
    stats = f"{len(nb.cells)} cells, {md.count('<details>')} solutions, {md.count('Saber mais')} 'Saber mais'"
    print(f"{'OK  ' if not problems else 'FAIL'} {path.relative_to(ROOT)}  ({stats})")
    for p in problems:
        print("      -", p)
    return problems


def main() -> int:
    targets = [Path(p).resolve() for p in sys.argv[1:]] or sorted(ROOT.glob("notebooks/*/*.ipynb"))
    return 1 if any([audit(p) for p in targets]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
