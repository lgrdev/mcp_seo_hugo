# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Internal-linking / SEO toolkit for a static **Hugo** site, shipped as a Claude Code plugin. No MCP server, no third-party Python package: the plugin is a CLI (`scripts/seoctl.py` + `scripts/seolib/`) driven by six skills, plus one subagent for the semantic judgement. Installing the plugin is the whole installation — `python3` is the only prerequisite.

Version 1.x was an MCP server (`scripts/hugo_seo_mcp.py`, fastmcp + NetworkX + ChromaDB + sentence-transformers). It worked, but required `pip install -r requirements.txt` and pulled torch (554.6 MB wheel) plus a 470 MB model. 2.0.0 replaced it; the logic was ported, not rewritten.

## Running

```bash
cd /path/to/hugo-project          # the directory that contains content/
python3 /path/to/plugin/scripts/seoctl.py audit
```

Tests: `pip install -r requirements-dev.txt && pytest` (pytest + PyYAML, nothing else). 69 tests, ~0.3 s. No build step, no linter config.

## Architecture

- Every command runs from the root of a Hugo project and reads `./content` (`config.CONTENT_DIR`). There is **no persisted state**: no vector store, no cache, no index file. An audit is recalculated from scratch in ~0.07 s, and BM25 ranking for 10 targets in ~0.56 s.
- `content.read_front_matter()` is a deliberately limited front-matter reader, not a YAML parser. It keeps non-indented `key: value` lines plus `  - item` lists that follow a valueless key, and skips every nested block (the corpus has `faq:` maps and multi-line JSON arrays). Only six top-level keys matter: `title`, `slug`, `aliases`, `draft`, `option_seo`, `robots`. A missing key falls back to the file stem, exactly as before — it never raises. `tests/test_frontmatter_oracle.py` checks it against PyYAML over all real corpus files; PyYAML is a test dependency only, never a runtime one, so behaviour cannot differ between machines.
- `content.load_pages()` parses `content/**/*.md` once and returns `(pages, skipped)` — every exclusion (unreadable encoding, `draft`, `option_seo: false`, `robots: noindex`) is recorded with its reason instead of being swallowed. A `noindex` page is out of scope by definition, so it needs no separate `option_seo` tag.
- `graph.resolve_target()` resolves an internal link by strict precedence (slug → alias → exact path → `path/<target>.md` → last segment). Substring matching was removed in 1.x: it made `/audit/` match three different pages non-deterministically. Unresolved targets are collected, not dropped silently.
- `graph.build_site()` returns a `Site` — `pages`, `out`, `inbound`, `skipped`, `unresolved` — where `out`/`inbound` are `{source: {target: anchor}}`. NetworkX was only ever used for degrees and predecessors, so two dicts replace it. Self-links are dropped: counting a page's link to itself would take it out of the orphan list for nothing.
- `rank.Bm25Index` (k1=1.5, b=0.75) replaces the ChromaDB semantic search. The query is the target page's title plus its description — the 1.x index was queried with the title alone, so the starting signal is the same or better. `rank.terms()` splits French elisions on apostrophes and lowercases, unlike `anchors.tokenize()` which keeps `d'Excel` in one piece for anchor text: without that split, a query term never matched an elided word in a paragraph.
- `rank.candidates_for()` excludes the target itself and every page that already links to it, and drops zero-score candidates rather than padding the list.
- The semantic judgement lives in `agents/link-picker.md`, because a skill cannot invoke another skill. The subagent reads the candidates JSON and writes a picks JSON; it never writes to `content/`. Keeping it in a subagent keeps ~3k tokens per target out of the main context.
- `seoctl.py proposals --from picks.json` refuses a pick whose `paragraph_text` is absent from the source file, or present more than once, before writing anything. The judge can paraphrase without meaning to; this turns that into a clear rejection instead of a later apply failure.
- `proposals.replace_paragraph()` is the single write path into `content/`. It refuses the edit when the paragraph occurs more than once (a blind first-occurrence replace could hit the wrong spot) and copies the file to `./.backups_seo/<run timestamp>/<path>` before the first write of a run.
- `proposals.apply_approved()` applies only blocks matching `[x] OUI` and stamps each processed block with `- **Statut :** APPLIQUÉ le …` / `ÉCHEC : …`. Idempotent: an already-`APPLIQUÉ` block is skipped on re-run. Blocks are rewritten back-to-front so the recorded offsets stay valid. `dry_run=True` writes nothing — neither content nor report.
- `anchors.insert_link()` builds the proposed paragraph deterministically: wrap the first unlinked in-prose occurrence of the target title's keywords as `[ancre](/slug/)`, else append `Pour aller plus loin : [Titre](/slug/).`. An `anchor_phrase` supplied by the judge is tried first and silently ignored when it is not present verbatim in the paragraph.
- Blocks that are mostly list items are excluded (`content.is_list_block`): an anchor injected into a bullet list reads badly, which is what the first real generated proposal did.
- `_index.md` pages are excluded from the orphan and under-linked lists: Hugo gives them inbound links through templates, not article bodies.
- `encoding.repair()` fixes files whose UTF-8 is broken by a known byte pattern. On this corpus the only corruption found was `C3 22` where `C3 BB` (`û`) was intended (106 occurrences across 23 files: "coût", "bien sûr"), so `BROKEN_SEQUENCES` maps exactly that. The fix is byte-level on purpose: re-decoding a whole file as cp1252 would turn its *valid* accents into mojibake. Anything not repaired by a known pattern is reported for manual handling, never guessed. Defaults to a dry run, backs up before writing.
- Measured parity with the 1.x MCP path on the real corpus: 91 pages, 37 internal links, 70 orphans, 2226 usable paragraphs — identical numbers, in 0.07 s instead of 39 s.
- What was lost by dropping embeddings: BM25 cannot relate two wordings with no shared term. The subagent compensates within the candidates it is given, but a good host paragraph outside the top N is gone. Measure it before assuming otherwise; do not re-add a vector store without that measurement.

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