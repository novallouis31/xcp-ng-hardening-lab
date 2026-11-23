#!/usr/bin/env python3
"""Markdown -> HTML -> PDF pour le lab (meme methode que pve9-hardening-lab).

Moteur : Chrome / Edge / Chromium headless, sans dependance tierce.
Les deux contournements heritage du lab Proxmox sont conserves :
  * profil utilisateur isole (aucun conflit avec un navigateur ouvert) ;
  * impression dans un fichier temporaire ASCII (les chemins avec espaces
    ou accents font echouer Chromium headless).

Usage :
    python scripts/pdf.py reports/report-final-xcp-ng-l3.md
    python scripts/pdf.py <entree.md> <sortie.pdf>
    python scripts/pdf.py --all            # tous les reports/*.md
    python scripts/pdf.py --all --docs     # reports/ + docs/
"""
from __future__ import annotations

import argparse
import html as html_mod
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Moteur de rendu ( porte de pve9-hardening-lab/scripts/pve_hardening/pdf.py )
# ---------------------------------------------------------------------------
_WINDOWS_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
)
_UNIX_CANDIDATES = (
    "google-chrome", "google-chrome-stable", "chromium",
    "chromium-browser", "microsoft-edge", "brave-browser",
)


class PdfError(RuntimeError):
    """Erreur de rendu PDF."""


def find_browser(preferred: str | None = None) -> str:
    """Retourne le chemin du premier moteur Chromium trouve."""
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    for var in ("CHROME_PATH", "BROWSER_PATH"):
        value = os.environ.get(var)
        if value:
            candidates.append(value)
    candidates.extend(_WINDOWS_CANDIDATES if os.name == "nt" else _UNIX_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    raise PdfError(
        "moteur Chromium introuvable. Installer Chrome/Edge/Chromium ou "
        "definir CHROME_PATH=/chemin/vers/le/binaire"
    )


def render_html_to_pdf(html: str | Path, pdf: str | Path,
                       browser: str | None = None) -> Path:
    """Convertit un fichier HTML en PDF et retourne le chemin produit."""
    html_path = Path(html).resolve()
    pdf_path = Path(pdf).resolve()
    if not html_path.exists():
        raise PdfError("HTML introuvable : {}".format(html_path))
    engine = find_browser(browser)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    src_uri = html_path.as_uri()

    tmp_dir = Path(tempfile.gettempdir())
    profile_dir = tmp_dir / ("lab-pdf-" + uuid.uuid4().hex)
    profile_dir.mkdir(parents=True, exist_ok=True)
    tmp_pdf = tmp_dir / ("lab-out-" + uuid.uuid4().hex + ".pdf")
    args = [
        engine, "--headless", "--disable-gpu", "--disable-extensions",
        "--no-first-run", "--no-sandbox", "--disable-setuid-sandbox",
        "--no-pdf-header-footer",
        "--user-data-dir={}".format(profile_dir),
        "--print-to-pdf={}".format(tmp_pdf),
        src_uri,
    ]
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=180, check=False)
        if proc.returncode != 0:
            raise PdfError("Chromium headless a echoue (code {}) : {}".format(
                proc.returncode,
                proc.stderr.decode("utf-8", "replace").strip()[-400:]))
        if not tmp_pdf.exists():
            raise PdfError("le PDF n'a pas ete produit : {}".format(tmp_pdf))
        shutil.move(str(tmp_pdf), str(pdf_path))
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
        if tmp_pdf.exists():
            tmp_pdf.unlink(missing_ok=True)
    print("  pdf    : {} ({:.1f} ko)".format(
        pdf_path, pdf_path.stat().st_size / 1024), flush=True)
    return pdf_path


# ---------------------------------------------------------------------------
# Markdown -> HTML ( porte de gen-validation-deharden.py )
# ---------------------------------------------------------------------------
_CSS = """
:root { --pass:#0a7d33; --fail:#c62828; --na:#6b7280; --ink:#111827; }
* { box-sizing:border-box; }
body { font-family:"Segoe UI",Calibri,Arial,Helvetica,sans-serif; color:var(--ink);
       margin:0; padding:0 0 24px; font-size:11pt; line-height:1.5; }
header { border-bottom:3px solid #111827; padding:18px 28px 12px; }
header h1 { font-size:19pt; margin:0 0 4px; }
header .meta { color:#4b5563; font-size:9.5pt; }
main { padding:0 28px; }
h1 { font-size:17pt; margin:24px 0 10px; }
h2 { font-size:14pt; margin:26px 0 10px; border-bottom:1px solid #e5e7eb; padding-bottom:4px; }
h3 { font-size:12pt; margin:20px 0 8px; }
table { border-collapse:collapse; width:100%; margin-bottom:10px; font-size:9.5pt; }
th { background:#111827; color:#fff; text-align:left; padding:6px 8px; font-weight:600; }
td { border-bottom:1px solid #e5e7eb; padding:5px 8px; vertical-align:top; }
tr:nth-child(even) td { background:#f9fafb; }
code { font-family:Consolas,"Courier New",monospace; font-size:9pt;
       background:#f3f4f6; padding:1px 4px; border-radius:3px; }
pre { background:#f3f4f6; border:1px solid #e5e7eb; border-radius:6px;
      padding:10px 12px; overflow-x:auto; }
pre code { background:none; padding:0; font-size:8pt; }
ul, ol { margin:6px 0 12px 22px; padding:0; }
li { margin:3px 0; }
blockquote { border-left:3px solid #9ca3af; margin:10px 0; padding:4px 12px; color:#4b5563; }
@page { size:A4; margin:14mm 12mm 14mm 12mm; }
""".strip()


def _md_inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append("<code>{}</code>".format(
                html_mod.escape(part[1:-1], quote=False)))
            continue
        escaped = html_mod.escape(part, quote=False)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                         r'<a href="\2">\1</a>', escaped)
        out.append(escaped)
    return "".join(out)


def _md_table(lines: list) -> str:
    def cells(line: str) -> list:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    header = cells(lines[0])
    body = [cells(line) for line in lines[2:]]
    out = ["<table>", "<thead><tr>"]
    out.extend("<th>{}</th>".format(_md_inline(c)) for c in header)
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        out.extend("<td>{}</td>".format(_md_inline(c)) for c in row)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def markdown_to_html(md: str, title: str) -> str:
    """Convertit le sous-ensemble Markdown utilise par les rapports."""
    lines = md.splitlines()
    body: list = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(html_mod.escape(lines[i], quote=False))
                i += 1
            i += 1
            body.append("<pre><code>{}</code></pre>".format("\n".join(block)))
            continue
        if stripped.startswith("|"):
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table.append(lines[i])
                i += 1
            body.append(_md_table(table))
            continue
        if stripped.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body.append("<blockquote>{}</blockquote>".format(
                _md_inline(" ".join(quote))))
            continue
        match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if match:
            level = len(match.group(1))
            body.append("<h{0}>{1}</h{0}>".format(
                level, _md_inline(match.group(2))))
            i += 1
            continue
        if re.match(r"^\d+\.\s", stripped) or stripped.startswith("- "):
            ordered = bool(re.match(r"^\d+\.\s", stripped))
            items = []
            while i < len(lines):
                current = lines[i].strip()
                if ordered and re.match(r"^\d+\.\s", current):
                    items.append(re.sub(r"^\d+\.\s+", "", current))
                elif not ordered and current.startswith("- "):
                    items.append(current[2:])
                elif current and items and not current.startswith(("#", "|", "```", ">")):
                    items[-1] += " " + current
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            body.append("<{0}>{1}</{0}>".format(
                tag, "".join("<li>{}</li>".format(_md_inline(it)) for it in items)))
            continue
        paragraph = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|\||```|\d+\.\s|- |> )", lines[i].strip()):
            paragraph.append(lines[i].strip())
            i += 1
        body.append("<p>{}</p>".format(_md_inline(" ".join(paragraph))))
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        '<title>{}</title><style>{}</style></head><body>'
        '<main>{}</main></body></html>'.format(
            html_mod.escape(title), _CSS, "\n".join(body))
    )


def md_to_pdf(source: Path, destination: Path | None = None,
              browser: str | None = None) -> Path:
    """Convertit un fichier Markdown en PDF (HTML intermediaire a cote)."""
    source = source.resolve()
    destination = (destination or source.with_suffix(".pdf")).resolve()
    md = source.read_text(encoding="utf-8", errors="replace")
    title = next((l.lstrip("# ").strip() for l in md.splitlines()
                  if l.startswith("# ")), source.stem)
    html_path = destination.with_suffix(".html")
    html_path.write_text(markdown_to_html(md, title), encoding="utf-8")
    print("[pdf] {} -> {}".format(source.name, destination.name), flush=True)
    return render_html_to_pdf(html_path, destination, browser)


def main() -> None:
    ap = argparse.ArgumentParser(description="Markdown -> PDF (Chrome headless)")
    ap.add_argument("source", nargs="?", type=Path, help="fichier .md source")
    ap.add_argument("destination", nargs="?", type=Path, help="fichier .pdf cible")
    ap.add_argument("--all", action="store_true", help="convertir tous les reports/*.md")
    ap.add_argument("--docs", action="store_true", help="avec --all, inclure docs/*.md")
    ap.add_argument("--browser", default=None, help="chemin d'un moteur Chromium")
    args = ap.parse_args()

    targets: list[Path] = []
    if args.all:
        targets += sorted((ROOT / "reports").glob("*.md"))
        if args.docs:
            targets += sorted((ROOT / "docs").glob("*.md"))
    elif args.source:
        targets.append(args.source)
    else:
        ap.error("indiquer un fichier .md ou --all")

    errors = 0
    for target in targets:
        try:
            md_to_pdf(target, args.destination if len(targets) == 1 else None,
                      args.browser)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print("  ERREUR {}: {}".format(target.name, exc), file=sys.stderr)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
