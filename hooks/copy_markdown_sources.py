"""MkDocs hook: publish raw English Markdown sources + generate llms-full.txt.

Why
---
LLM coding agents (Cursor, Windsurf, Claude Code) parse the web much
better when they can fetch raw Markdown instead of the rendered HTML
(less noise, no UI scaffolding). On a static GitHub Pages host we
cannot do server-side `Accept: text/markdown` content negotiation, so
we publish the .md sources at a stable URL and concatenate them into
a single /llms-full.txt for one-shot agent context windows.

What it does
------------
1. Walks `docs/` for English Markdown files (skips translations
   matching `*.{fr,de,es,it,pt,zh,ja,ko}.md`).
2. Copies each `.md` to `site/markdown/<same-relative-path>` so the
   sources stay at predictable URLs.
3. Concatenates all of them (in stable alphabetical order) into a
   single `site/llms-full.txt` with per-file headers so agents can
   ingest the entire English documentation in a single fetch.

The hook is idempotent — running it multiple times during the i18n
build is safe (overwrites are the same content).
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

# Locale codes that mark translated `*.<locale>.md` files we must skip.
# Keep in sync with the languages declared in mkdocs.yml > plugins > i18n.
_TRANSLATION_LOCALES = frozenset({
    "fr", "de", "es", "it", "pt", "zh", "ja", "ko",
})


def _is_translation(rel_path: Path) -> bool:
    """Return True if filename ends with `.<locale>.md`."""
    parts = rel_path.name.split(".")
    return len(parts) >= 3 and parts[-2] in _TRANSLATION_LOCALES


def on_post_build(config, **kwargs) -> None:
    docs_dir = Path(config["docs_dir"])
    site_dir = Path(config["site_dir"])

    out_dir = site_dir / "markdown"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    md_files: list[tuple[Path, Path]] = []
    for md in sorted(docs_dir.rglob("*.md")):
        rel = md.relative_to(docs_dir)
        if _is_translation(rel):
            continue
        # Skip docs/.well-known/* and other generated artefacts that
        # should not be exposed as English documentation.
        if rel.parts and rel.parts[0].startswith("."):
            continue
        md_files.append((rel, md))

    parts: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(
        "# asiai — full documentation (English)\n"
        "\n"
        f"Generated: {now}\n"
        f"Pages: {len(md_files)}\n"
        "Source: https://github.com/druide67/asiai/tree/main/docs\n"
        "License: Apache-2.0\n"
        "\n"
        "This file concatenates every English Markdown page so an AI agent "
        "can ingest the whole documentation in one fetch. Per-page raw "
        "sources are also available individually under "
        "https://asiai.dev/markdown/<relative-path>.\n"
    )

    for rel, src in md_files:
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

        try:
            content = src.read_text(encoding="utf-8")
        except Exception:
            content = "(unreadable)"
        url_path = rel.with_suffix("").as_posix()
        parts.append(
            "\n\n---\n\n"
            f"## /{url_path}\n"
            f"\n"
            f"Raw markdown: https://asiai.dev/markdown/{rel.as_posix()}\n"
            f"Rendered: https://asiai.dev/{url_path}/\n"
            f"\n"
            f"{content}"
        )

    full_path = site_dir / "llms-full.txt"
    full_path.write_text("\n".join(parts), encoding="utf-8")

    print(
        f"[copy_markdown_sources] copied {len(md_files)} .md sources "
        f"to {out_dir}/ and wrote {full_path} "
        f"({full_path.stat().st_size:,} bytes)"
    )
