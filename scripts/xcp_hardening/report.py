"""Build a Markdown diff report from audit/func artifacts (no hard-coded numbers)."""
from __future__ import annotations

from pathlib import Path

from .config import ROOT


def parse_checks(path: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            out[parts[0]] = (parts[1], parts[2])
            continue
        if line.startswith("@@CHECK "):
            p = line.split(maxsplit=3)
            if len(p) >= 4:
                out[p[1]] = (p[2], p[3])
    return out


def parse_tests(path: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("@@TEST "):
            p = line.split(maxsplit=3)
            if len(p) >= 4:
                out[p[1]] = (p[2], p[3])
    return out


def build_report(before: Path, after: Path, title: str) -> str:
    b, a = parse_checks(before / "checks.tsv"), parse_checks(after / "checks.tsv")
    fb, fa = parse_tests(before / "fonctionnel.txt"), parse_tests(after / "fonctionnel.txt")
    ids = sorted(set(b) | set(a))
    lines = [
        f"# {title}", "",
        f"- before: `{before.name}`", f"- after: `{after.name}`",
        f"- controls: {len(ids)}", f"- functional tests: {len(set(fb) | set(fa))}", "",
        "## Compliance changes", "", "| ID | Before | After | Detail |", "| --- | --- | --- | --- |",
    ]
    regressions = 0
    improvements = 0
    for i in ids:
        bs, bt = b.get(i, ("MISSING", ""))
        as_, at = a.get(i, ("MISSING", ""))
        if bs != as_:
            if as_ == "PASS" and bs != "PASS":
                improvements += 1
            if as_ == "FAIL" and bs == "PASS":
                regressions += 1
        lines.append(f"| {i} | {bs} | {as_} | {at or bt} |")
    lines += ["", f"improvements={improvements}, regressions={regressions}", "", "## Functional tests", "", "| ID | Before | After |", "| --- | --- | --- |"]
    freg = 0
    for i in sorted(set(fb) | set(fa)):
        bs = fb.get(i, ("MISSING", ""))[0]
        as_ = fa.get(i, ("MISSING", ""))[0]
        if bs != "FAIL" and as_ == "FAIL":
            freg += 1
        lines.append(f"| {i} | {bs} | {as_} |")
    lines += ["", f"functional regressions={freg}", ""]
    return "\n".join(lines)


def save(artifacts: list[Path], title: str) -> Path:
    if len(artifacts) < 2:
        raise ValueError("need at least two artifact directories")
    text = build_report(artifacts[0], artifacts[-1], title)
    path = ROOT / "reports"
    path.mkdir(exist_ok=True)
    out = path / f"report-{title.lower().replace(' ', '-')}.md"
    out.write_text(text, encoding="utf-8")
    print(out)
    return out
