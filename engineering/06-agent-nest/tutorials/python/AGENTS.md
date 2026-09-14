# AGENTS.md — learn-claude-code

## Project

An educational repo that teaches how to build an AI coding agent harness. 20 progressively more complex chapters (s01–s20), each implementing one harness mechanism on top of the core agent loop. Two implementation tracks: Python (complete, in `sXX_*/code.py`) and Rust (in progress, in `rust/sXX_*/src/main.rs`). The Python versions are the canonical reference; the Rust versions are being written to match them chapter by chapter.

Core philosophy: the model supplies intelligence; the harness supplies tools, knowledge, permissions, and context. The agent loop never changes — only the mechanisms around it do.

## Environment

- Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` + `MODEL_ID`
- Optional: `ANTHROPIC_BASE_URL` for third-party Anthropic-compatible gateways
- Optional: `EFFORT_LEVEL` (low/medium/high/xhigh/max), `MAX_TOKENS`, `ANTHROPIC_BETA`

## Common Commands

### Python (canonical reference)

```bash
pip install -r requirements.txt
python sXX_*/code.py          # run a single chapter
```

### Rust (complete, s01-s20)

```bash
cargo run -p s01_agent_loop   # run a Rust chapter (replace s01 with any chapter)
S01_DEBUG=1 cargo run -p s01_agent_loop  # debug: print raw API request/response
cargo test -p s01_agent_loop  # run tests for a specific chapter
cargo test --workspace        # run all Rust tests
```

Manual end-to-end testing guide: `rust/TEST.md` (T1–T17 cover s01–s20, track complete).

All Rust crates in the workspace share the same root-level `.env` file. The `dotenvy` crate tries `.env` in both `rust/` and `../`.

## Architecture

```
s01_agent_loop/         # Python: each chapter is self-contained
├── code.py             #   runnable reference implementation
├── README.md           #   narrative tutorial (zh)
├── README.en.md        #   English translation
├── README.ja.md        #   Japanese translation
└── images/             #   diagrams
...
s20_comprehensive/

rust/                   # Rust: cargo workspace, one binary crate per chapter
├── Cargo.toml          #   workspace manifest (members: s01..s20)
├── s01_agent_loop/     #   each crate is self-contained (copy-paste, by design)
│   ├── Cargo.toml
│   └── src/main.rs
...
└── s20_comprehensive/

skills/                 # Example skill definitions (agent-builder, code-review, mcp-builder, pdf)
tests/                  # Python unit/smoke tests for chapter code
web/                    # Next.js doc site rendering the s01-s20 chapters
```

## Rust Implementation Status

| Chapter | Status | Lines | Topic |
|---|---:|---|
| s01 | done | 705 | Agent loop + bash + Anthropic API via reqwest |
| s02 | done | 1003 | 5 tools (bash/read/write/edit/glob) + match dispatch |
| s03 | done | 1263 | 3-gate permission system (deny→rules→confirm) |
| s04 | done | 1714 | Hook system (4 event types + 5 built-in hooks) |
| s05 | done | 1907 | TodoWrite planning tool + nag reminder |
| s06 | done | 2254 | Subagent with context isolation |
| s07 | done | 2584 | Skill loading + YAML frontmatter parsing |
| s08 | done | 3096 | Context compaction (4-layer pipeline, tail-keeping) |
| s09 | done | 3538 | Persistent `.memory/` files + index |
| s10 | done | 3663 | Dynamic system prompt assembly (5 sections) + caching |
| s11 | done | 4270 | Error recovery (escalate/continue/compact/backoff/fallback) |
| s12 | done | 4823 | Persistent `.tasks/` task graph + blockedBy deps + 5 task tools |
| s13 | done | 5684 | Background tasks + SSE streaming + parallel tool execution (first tokio chapter) |
| s14 | done | 6633 | Cron scheduler: 5-field matching + durable `.scheduled_tasks.json` + select! auto-delivery |
| s15 | done | 7439 | Agent teams: file mailbox MessageBus + teammate tokio tasks + Lead wake injection (select! 3rd branch) |
| s16 | done | 8477 | Team protocols: ProtocolState state machine + request_id handshake + plan approval + teammate idle loop |
| s17 | done | 8758 | Autonomous agents: task board scan + auto-claim + 60s bounded idle poll + identity re-injection |
| s18 | done | 9388 | Worktree isolation: git worktree per task + task binding + teammate cwd switching + change protection |
| s19 | done | 10345 | MCP plugin: MCPClient (mock) + .mcp.json config-driven servers + assemble_tool_pool dynamic tool pool + dual-path dispatch |
| s20 | done | 10470 | Comprehensive: all mechanisms in one loop + MCP tools in permission pipeline (Gate 3) + Current time section + Skills catalog |

### Key Rust Conventions

- **Self-contained chapters**: each crate copies the full data model (`ContentBlock`, `Message`, `ApiRequest`, etc.) rather than sharing a library crate. This is intentional for teaching — each chapter is independently readable and runnable. Extraction into a shared crate is deferred until the full 20-chapter implementation stabilizes.
- **Blocking reqwest**: uses `reqwest::blocking` with `rustls-tls`. No tokio needed until s13 (async & concurrency: background tasks, SSE streaming, parallel tool execution).
- **Strongly-typed tool inputs**: each tool has a `#[derive(Deserialize)]` struct for parameter validation at deserialization time rather than manual JSON field access.
- **Reader injection for testing**: gate 3 (user confirmation) takes a reader instead of reading stdin directly, so tests use `Cursor<&str>` to simulate keyboard input. s03–s13 use `&mut impl BufRead`; s14+ uses `&mut impl Read` backed by `RawStdin` (`libc::read` on fd 0) — the change bypasses std's global stdin mutex, which the REPL's tokio stdin background read thread holds while blocked (cron turns stalled until Enter; fixed 2026-08).
- **`Option<String>` for hook results**: `Some(reason)` means blocked/stop-requested; `None` means pass-through.
- **Truncation by line**: `truncate_lines()` cuts output at line boundaries, appends `"..."`. Never splits mid-line or mid-UTF-8.
- **Chinese comments**: module-level doc comments (`//!`) and section headers are in Chinese, matching the primary README language. Inline comments on tricky Rust semantics are in English.

### Dependencies (per crate)

```toml
reqwest = { version = "0.12", default-features = false, features = ["blocking", "json", "rustls-tls"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
dotenvy = "0.15"
wait-timeout = "0.2"
glob = "0.3"
```

Already in use: `serde_yaml` (s07+, skill frontmatter), `rand` (s11+, backoff jitter), `tokio` (s13+, async runtime: background tasks, SSE streaming, parallel tool execution), `chrono` (s14+, local time & calendar fields for cron matching). Future chapters may add: `anyhow`, `uuid`.

## Key Patterns (Python & Rust)

### The Agent Loop (never changes)

```text
while stop_reason == "tool_use":
    response = LLM(messages, tools)
    execute tools → collect tool_results
    append results to messages
```

The model decides when to stop. The harness just executes what the model asks for.

### Chapter Progression

Each chapter adds exactly one mechanism, layered on the previous:

| Ch | Mechanism | What it adds |
|---|---|---|
| s01 | Agent Loop | while loop + bash + API client |
| s02 | Tool Use | 4 more tools + match dispatch + safe_path |
| s03 | Permission | 3 gates (deny list → rules → user confirm) |
| s04 | Hooks | PreToolUse/PostToolUse/Stop/UserPromptSubmit events |
| s05 | TodoWrite | Planning tool + nag reminder |
| s06 | Subagent | Spawn isolated agent with own messages |
| s07 | Skill Loading | On-demand skill file loading |
| s08 | Context Compact | 4-layer compression pipeline |
| s09 | Memory | Persistent `.memory/` files with frontmatter |
| s10 | System Prompt | Runtime prompt assembly from context |
| s11 | Error Recovery | Error classification and retry |
| s12 | Task System | Persistent `.tasks/` with dependency graph |
| s13 | Async & Concurrency | Background tasks + streaming output + parallel tool execution |
| s14 | Cron Scheduler | Scheduled task threads |
| s15 | Agent Teams | File-based inbox + parallel teammate threads |
| s16 | Team Protocols | Request-response handshake protocol |
| s17 | Autonomous Agents | Idle polling auto-claim tasks |
| s18 | Worktree Isolation | Git worktree per agent |
| s19 | MCP Plugin | MCP external tool routing |
| s20 | Comprehensive | All mechanisms combined |

## Writing a New Rust Chapter

1. Copy the previous chapter's `src/main.rs` as a starting point
2. Read the corresponding Python `sXX_*/code.py` for the reference behavior
3. Read `sXX_*/README.md` for the narrative explanation and diagrams
4. Add the new mechanism; keep existing mechanisms unchanged
5. Update the `Cargo.toml` dependencies if new crates are needed
6. Write unit tests for the new mechanism's pure functions
7. Write `rust/sXX_*/README.md`, following the previous chapter's README structure (mechanism diagram, "changes from previous chapter" table, how to run, key design decisions, file tree, current test count, comparison with the Python version, next-chapter table)
8. Run `cargo test -p sXX_*` and `cargo run -p sXX_*` to verify
9. Update the progress checklist in `rust/README.md`
10. Update `rust/TEST.md`: the new chapter is the new cumulative chapter — re-point the crate name, append a new test path (T8, T9, …), and refresh the test counts (see its section 8)

When implementing a new chapter, do NOT refactor or restructure earlier chapters. Each chapter is frozen once completed. If a pattern needs improvement, apply it forward to the new chapter only.
