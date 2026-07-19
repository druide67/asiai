"""MkDocs hook: derive a per-locale sitemap.xml from the root sitemap.

Material's language selector fetches ``<locale>/sitemap.xml`` for every
``link[rel=alternate]`` in the head (to map the current page to its
localized equivalent). mkdocs-static-i18n only emits the root sitemap,
so every page view fired one 404 per locale — harmless functionally
(Material swallows the failure) but it litters the console and costs
the Lighthouse best-practices score.

This hook splits the root sitemap after the build: each locale gets a
sitemap.xml (and .xml.gz, matching MkDocs) containing only the URLs
under its own prefix. The root sitemap — the one search engines are
pointed at — is left untouched.
"""

from __future__ import annotations

import gzip

# stdlib ElementTree is fine here: the parsed file is our own build
# artifact (MkDocs just wrote it), never external input — no XXE surface.
import xml.etree.ElementTree as ET
from pathlib import Path

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_XHTML_NS = "http://www.w3.org/1999/xhtml"


def _locales(config) -> list[str]:
    """Non-default locale codes from the i18n plugin config."""
    for name, plugin in config["plugins"].items():
        if name == "i18n" or name.endswith("/i18n"):
            return [
                lang.locale
                for lang in plugin.config["languages"]
                if lang.build and not lang.default
            ]
    return []


def on_post_build(config, **kwargs):
    site_dir = Path(config["site_dir"])
    root_sitemap = site_dir / "sitemap.xml"
    if not root_sitemap.exists():
        return

    site_url = config["site_url"].rstrip("/")
    ET.register_namespace("", _SITEMAP_NS)
    ET.register_namespace("xhtml", _XHTML_NS)
    tree = ET.parse(root_sitemap)

    written = 0
    for locale in _locales(config):
        prefix = f"{site_url}/{locale}/"
        urlset = ET.Element(f"{{{_SITEMAP_NS}}}urlset")
        for url in tree.getroot():
            loc = url.find(f"{{{_SITEMAP_NS}}}loc")
            if loc is None or loc.text is None:
                continue
            if loc.text == prefix or loc.text.startswith(prefix):
                urlset.append(url)
        out_dir = site_dir / locale
        if not out_dir.is_dir() or len(urlset) == 0:
            continue
        payload = ET.tostring(urlset, encoding="UTF-8", xml_declaration=True)
        (out_dir / "sitemap.xml").write_bytes(payload)
        # mtime=0 keeps rebuilds byte-identical (gzip stores a timestamp).
        (out_dir / "sitemap.xml.gz").write_bytes(gzip.compress(payload, mtime=0))
        written += 1
    print(f"[gen_locale_sitemaps] wrote {written} locale sitemaps")
