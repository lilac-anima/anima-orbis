# Anima Orbis

A static website generated from the Anima Orbis Obsidian vault.

## Local preview

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

Then open <http://localhost:8000>.

## Cloudflare Pages

- Build command: `python3 scripts/build.py`
- Output directory: `dist`
- Production branch: `main`

The build reads the Markdown notes and media in this repository. Obsidian workspace settings are ignored and are not published.
