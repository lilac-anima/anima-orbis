#!/usr/bin/env python3
"""Build a small, dependency-free static site from the Anima Orbis vault."""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"
SKIP_DIRS = {".obsidian", ".git", "dist", "_site", "_build", "scripts"}


def slug(path: Path) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", path.stem).strip("-").lower()
    return text or "page"


def discover_notes() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        rel = path.relative_to(ROOT)
        result[str(rel)] = "index.html" if rel.name == "Anima Orbis.md" else f"{slug(rel)}.html"
    return result


def link_for(target: str, notes: dict[str, str]) -> str | None:
    target = target.split("|", 1)[0].strip()
    if target.startswith("#"):
        return target
    target = target.split("#", 1)[0].strip()
    if not target:
        return None
    wanted = Path(target).stem.lower()
    for source, output in notes.items():
        if Path(source).stem.lower() == wanted:
            return output
    return None


def inline(text: str, notes: dict[str, str]) -> str:
    # Obsidian embeds and wikilinks.
    def embed(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        if raw.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
            src = quote(raw, safe="/.:_-()")
            return f'<img src="{src}" alt="{html.escape(Path(raw).stem)}">'
        destination = link_for(raw, notes)
        return f'<a href="{destination or "#"}">{html.escape(Path(raw).stem)}</a>'

    text = re.sub(r"!\[\[([^\]]+)\]\]", embed, text)

    def wiki(match: re.Match[str]) -> str:
        raw = match.group(1)
        label = raw.split("|", 1)[-1].split("#", 1)[0].strip()
        destination = link_for(raw, notes)
        return f'<a href="{destination or "#"}">{html.escape(label)}</a>'

    text = re.sub(r"\[\[([^\]]+)\]\]", wiki, text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: f'<img src="{quote(m.group(2), safe="/.:_-()")}" alt="{html.escape(m.group(1))}">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{m.group(2)}">{html.escape(m.group(1))}</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def markdown_to_html(source: str, notes: dict[str, str]) -> str:
    # Convert local Obsidian file URLs to deployable root-relative URLs.
    source = re.sub(r'file:///[^\"]*/Animations/', '/Animations/', source)
    raw_lines = source.splitlines()
    # Preserve multiline raw HTML blocks such as iframe embeds as one block.
    lines: list[str] = []
    html_block: list[str] = []
    in_html_block = False
    for raw in raw_lines:
        if not in_html_block and raw.lstrip().startswith("<iframe"):
            in_html_block = True
            html_block = [raw]
        elif in_html_block:
            html_block.append(raw)
            if "</iframe>" in raw:
                lines.append("\\n".join(html_block))
                html_block = []
                in_html_block = False
        else:
            lines.append(raw)
    if html_block:
        lines.append("\\n".join(html_block))
    out: list[str] = []
    paragraph: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph), notes)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        if line.strip().startswith("```"):
            flush(); close_list()
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush(); close_list(); continue
        if line.lstrip().startswith("<") or line.lstrip().startswith("</"):
            flush(); close_list(); out.append(line); continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush(); close_list()
            text = inline(heading.group(2), notes)
            anchor = re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", heading.group(2).lower()))
            out.append(f'<h{len(heading.group(1))} id="{anchor}">{text}</h{len(heading.group(1))}>')
            continue
        item = re.match(r"^\s*[-*]\s+(.+)$", line)
        if item:
            flush()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(item.group(1), notes)}</li>")
            continue
        flush() if line.startswith("!") else None
        paragraph.append(line.strip())
    flush(); close_list()
    return "\n".join(out)


def page(title: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · Anima Orbis</title><link rel="stylesheet" href="style.css"></head>
<body><header><a class="brand" href="index.html">Anima Orbis</a><nav><a href="index.html">Home</a><a href="shape-sandbox.html">Sandbox</a></nav></header>
<main><article>{body}</article></main><footer>Anima Orbis · movement, props, and practice</footer></body></html>'''


def main() -> None:
    notes = discover_notes()
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts): continue
        if path.suffix.lower() == ".md": continue
        destination = OUT / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    for source, output in notes.items():
        path = ROOT / source
        body = markdown_to_html(path.read_text(encoding="utf-8"), notes)
        title = path.stem
        (OUT / output).write_text(page(title, body), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    print(f"Built {len(notes)} pages and copied media to {OUT}")


CSS = """*{box-sizing:border-box}body{margin:0;color:#24302d;background:#f6f3ec;font:16px/1.65 system-ui,sans-serif}header{display:flex;justify-content:space-between;align-items:center;padding:1rem max(1.25rem,calc((100vw - 980px)/2));background:#203b36;color:#fff}header a{color:inherit;text-decoration:none;margin-left:1rem}.brand{font-weight:700;font-size:1.15rem;margin-left:0}main{max-width:980px;margin:3rem auto;padding:0 1.25rem}article{background:#fffdf8;padding:clamp(1.5rem,5vw,4rem);border:1px solid #e3ded2;border-radius:14px;box-shadow:0 8px 30px #203b3610}h1,h2,h3{line-height:1.2;color:#203b36}h1{font-size:clamp(2rem,5vw,3.5rem)}a{color:#9a4f35}img{max-width:100%;height:auto}iframe{max-width:100%;background:#f1eee7}pre{overflow:auto;background:#203b36;color:#fff;padding:1rem;border-radius:8px}footer{text-align:center;color:#68736e;padding:2rem 1rem 3rem}li{margin:.3rem 0}"""

if __name__ == "__main__": main()
