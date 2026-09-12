# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MCP (Model Context Protocol) server exposing internal-linking / SEO tools for a static **Hugo** site. Single-file implementation: `scripts/hugo_seo_mcp.py`, built on `fastmcp`.

## Running

```bash
pip install fastmcp python-frontmatter networkx chromadb sentence-transformers
python scripts/hugo_seo_mcp.py
```

Tests: `pip install -r requirements-dev.txt && pytest`. `tests/conftest.py` stubs `fastmcp` and `chromadb` so the suite covers the pure logic without pulling torch; anything that needs a real embedding index stays manual. No build step, no linter config.

## Architecture

- The server expects to be run with the current working directory set to the root of a Hugo project — it reads Markdown from a hardcoded relative path `./content` (`CONTENT_DIR` in `scripts/hugo_seo_mcp.py`) and persists a Chroma vector store at `./.chroma_seo`.
- `load_pages()` parses `content/**/*.md` once and returns `(pages, skipped)` — every exclusion (unreadable encoding, bad front matter, `draft`, `option_seo: false`, `robots: noindex`) is recorded with its reason instead of being swallowed. A `noindex` page is out of scope by definition, so it needs no separate `option_seo` tag. `sync_and_get_site_audit` reuses that single parse for both the graph and the ChromaDB chunking.
- `_resolve_target()` resolves an internal link by strict precedence (slug → alias → exact path → `path/<target>.md` → last segment). Substring matching was removed: it made `/audit/` match three different pages non-deterministically. Unresolved targets are collected, not dropped silently.
- `build_graph()` / `graph_from_pages()` build a NetworkX `DiGraph` and stash diagnostics in `G.graph["skipped"]` and `G.graph["unresolved"]`, which the audit surfaces. It walks `content/**/*.md`, skips drafts and pages with front matter `option_seo: false`, and builds the graph where nodes are Hugo pages (keyed by path relative to `content/`) and edges are internal Markdown links (`[text](target)`) resolved by matching the link target against page paths/slugs. This graph is rebuilt from scratch on every tool call that needs it — there is no caching between calls.
- Six MCP tools are exposed. Tools 1-3 are the agent-driven flow, tools 4-6 the file-based human review loop (`sync_and_get_site_audit` → `generate_proposals_report` → user ticks `[x] OUI` → `apply_approved_proposals` → `archive_proposals_report`):
  1. `sync_and_get_site_audit` — rebuilds the link graph, fully re-indexes all non-draft, `option_seo`-enabled page content into the ChromaDB `hugo_seo` collection (chunked by blank-line paragraphs, ≥80 chars, code blocks/images/headings stripped), writes an HTML audit report to `./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html` (orphan pages, link counts), and returns the same summary as text plus the report path.
  2. `find_link_opportunities` — semantic search (via the Chroma collection populated by tool 1) for paragraphs elsewhere in the site that are good candidates to link to a given `target_path`, excluding pages that already link to it.
  3. `update_markdown_paragraph` — does an exact string replace of one paragraph in a source `.md` file, used to insert the anchor link chosen by the calling agent. Front matter is left untouched since only `post.content` (frontmatter-stripped body) is ever searched, but the replace itself operates on the raw file text.
  4. `generate_proposals_report` — writes one proposal per orphan/under-linked page (in-degree ≤ `UNDERLINKED_MAX_IN_DEGREE`, `_index.md` pages excluded as their slug makes no URL) to `./propositions_seo.md`, each with an unchecked `- **Validation :** [ ] OUI / [ ] NON` box and the original/proposed paragraph in `text` fences. The proposed paragraph is built deterministically by `_insert_link()`: wrap the first unlinked in-prose occurrence of the target title's keywords as `[ancre](/slug/)`, else append `Pour aller plus loin : [Titre](/slug/).`. One proposal per source paragraph.
  5. `apply_approved_proposals(dry_run=False)` — parses the report (`_parse_proposals`, tolerant of spacing/case), applies only blocks matching `[x] OUI`, and stamps each processed block with `- **Statut :** APPLIQUÉ le …` / `ÉCHEC : …`. Idempotent: an already-`APPLIQUÉ` block is skipped on re-run. Blocks are rewritten back-to-front so the recorded offsets stay valid. `dry_run=True` reports what would change and writes nothing — neither content nor report.
  6. `archive_proposals_report` — moves the report to `./.archives_seo/propositions_YYYYMMDD_HHMMSS.md` and recreates it with `PROPOSALS_HEADER` only.
  7. `repair_content_encoding(dry_run=True)` — fixes files whose UTF-8 is broken by a known byte pattern. On this corpus the only corruption found was `C3 22` where `C3 BB` (`û`) was intended (106 occurrences across 23 files: "coût", "bien sûr"), so `BROKEN_SEQUENCES` maps exactly that. The fix is byte-level on purpose: re-decoding a whole file as cp1252 would turn its *valid* accents into mojibake. Anything not repaired by a known pattern is reported for manual handling, never guessed. Backs up to `./.backups_seo/<timestamp>/` and defaults to a dry run.
  8. `get_index_status()` — read-only "where am I": pages in scope, indexable paragraph count, index size and recorded model, drift (chunks to encode / obsolete), unreadable files, last audit, pending proposals. It deliberately calls `chroma_client.get_collection()` **without** an embedding function: that path measures ~1 ms and never loads the model, so status stays ~76 ms against the ~9 s a model load would cost. Drift is computed by re-running `build_chunks()` (pure text, no encoding) and diffing ids against the collection — comparing page paths alone would report false positives, since a short or list-only page legitimately has no chunk.
- `@mcp.tool()` registers the tool but returns the plain function in the installed fastmcp version, so tools remain directly callable. Even so, shared logic lives in `_`-prefixed helpers (`_find_link_opportunities`, `_replace_paragraph`) that both the tool wrappers and the new tools call, rather than tools calling each other.
- Because `update_markdown_paragraph` matches on exact paragraph text, callers must pass back the *exact* `paragraph_text` returned by `find_link_opportunities` (whitespace and all) as `old_paragraph`, or the replace fails.
- `_replace_paragraph()` is the single write path into `content/`. It refuses the edit when the paragraph occurs more than once (a blind first-occurrence replace could hit the wrong spot) and copies the file to `./.backups_seo/<run timestamp>/<path>` before the first write of a run.
- The ChromaDB collection is built with an explicit multilingual embedding function (`EMBEDDING_MODEL`, `paraphrase-multilingual-MiniLM-L12-v2`) because the corpus is French; Chroma's bundled default is English-only. The model name is stored in the collection metadata and `find_link_opportunities` refuses to query an index built with a different model rather than return silently-wrong neighbours. First run downloads the model (~500 MB with torch).
- Blocks that are mostly list items are excluded from indexing (`_is_list_block`): an anchor injected into a bullet list reads badly, which is what the first real generated proposal did.
- Indexing is incremental (`_sync_collection`). Chunk ids are content-addressed (`<path>#<sha1[:12]>`) rather than positional, so inserting a paragraph does not invalidate the ones after it; the sync adds only new ids, deletes obsolete ones, and reuses the rest. Measured on this corpus: a full index is ~39 s but ~99.9 % of that is embedding (model load ~9 s, encoding 2226 paragraphs ~41 s) while all graph/parse work is ~33 ms — so a no-change sync drops to 0.1 s warm, and a one-paragraph edit re-encodes exactly one chunk. Optimising the Python side would be pointless; don't.
- `_index.md` pages are excluded from the orphan and under-linked lists: Hugo gives them inbound links through templates, not article bodies.
- The Chroma collection is dropped and recreated on every `sync_and_get_site_audit` call rather than incrementally updated.

# Codebase Analysis Priority 
- Always use codebase-memory-mcp tools (like trace_call_path, search_graph) to explore the codebase or answer structural questions. 
- Fallback to standard grep or file reading only if the MCP graph returns insufficient data.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
rtk uv run <cmd>        # Compact uv project command output
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->