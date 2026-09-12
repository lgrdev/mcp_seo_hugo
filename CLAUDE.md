# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MCP (Model Context Protocol) server exposing internal-linking / SEO tools for a static **Hugo** site. Single-file implementation: `scripts/hugo_seo_mcp.py`, built on `fastmcp`.

## Running

```bash
pip install fastmcp python-frontmatter networkx chromadb sentence-transformers
python scripts/hugo_seo_mcp.py
```

No build step, no test suite, no linter config exist in this repo.

## Architecture

- The server expects to be run with the current working directory set to the root of a Hugo project — it reads Markdown from a hardcoded relative path `./content` (`CONTENT_DIR` in `scripts/hugo_seo_mcp.py`) and persists a Chroma vector store at `./.chroma_seo`.
- `build_graph()` is the core in-memory model: it walks `content/**/*.md`, skips drafts, and builds a NetworkX `DiGraph` where nodes are Hugo pages (keyed by path relative to `content/`) and edges are internal Markdown links (`[text](target)`) resolved by matching the link target against page paths/slugs. This graph is rebuilt from scratch on every tool call that needs it — there is no caching between calls.
- Three MCP tools are exposed, meant to be called in sequence by the calling agent:
  1. `sync_and_get_site_audit` — rebuilds the link graph, fully re-indexes all non-draft page content into the ChromaDB `hugo_seo` collection (chunked by blank-line paragraphs, ≥80 chars, code blocks/images/headings stripped), and returns orphan pages (in-degree 0) plus link counts.
  2. `find_link_opportunities` — semantic search (via the Chroma collection populated by tool 1) for paragraphs elsewhere in the site that are good candidates to link to a given `target_path`, excluding pages that already link to it.
  3. `update_markdown_paragraph` — does an exact string replace of one paragraph in a source `.md` file, used to insert the anchor link chosen by the calling agent. Front matter is left untouched since only `post.content` (frontmatter-stripped body) is ever searched, but the replace itself operates on the raw file text.
- Because `update_markdown_paragraph` matches on exact paragraph text, callers must pass back the *exact* `paragraph_text` returned by `find_link_opportunities` (whitespace and all) as `old_paragraph`, or the replace fails.
- The Chroma collection is dropped and recreated on every `sync_and_get_site_audit` call rather than incrementally updated.
