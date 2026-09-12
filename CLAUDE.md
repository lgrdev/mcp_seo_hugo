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
- `build_graph()` is the core in-memory model: it walks `content/**/*.md`, skips drafts and pages with front matter `option_seo: false`, and builds a NetworkX `DiGraph` where nodes are Hugo pages (keyed by path relative to `content/`) and edges are internal Markdown links (`[text](target)`) resolved by matching the link target against page paths/slugs. This graph is rebuilt from scratch on every tool call that needs it — there is no caching between calls.
- Three MCP tools are exposed, meant to be called in sequence by the calling agent:
  1. `sync_and_get_site_audit` — rebuilds the link graph, fully re-indexes all non-draft, `option_seo`-enabled page content into the ChromaDB `hugo_seo` collection (chunked by blank-line paragraphs, ≥80 chars, code blocks/images/headings stripped), writes an HTML audit report to `./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html` (orphan pages, link counts), and returns the same summary as text plus the report path.
  2. `find_link_opportunities` — semantic search (via the Chroma collection populated by tool 1) for paragraphs elsewhere in the site that are good candidates to link to a given `target_path`, excluding pages that already link to it.
  3. `update_markdown_paragraph` — does an exact string replace of one paragraph in a source `.md` file, used to insert the anchor link chosen by the calling agent. Front matter is left untouched since only `post.content` (frontmatter-stripped body) is ever searched, but the replace itself operates on the raw file text.
- Because `update_markdown_paragraph` matches on exact paragraph text, callers must pass back the *exact* `paragraph_text` returned by `find_link_opportunities` (whitespace and all) as `old_paragraph`, or the replace fails.
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