# CLAUDE.md — guidance for Claude Code in this repo

## What this project is

A single-file FastAPI service (`server.py`) that exposes the user's running
tmux server over HTTP, using `libtmux`. Packaged with a Nix flake.

## Critical safety rule

**The server connects to the user's default tmux socket — the same one
running their real work.** Never run any command that affects the whole tmux
server or untargeted sessions. Forbidden:

- `tmux kill-server`
- `tmux kill-session` without `-t <specific-name>`
- `libtmux.Server().kill()` / `Server.kill_server()`
- `pkill tmux`, `killall tmux`

For testing, create sessions with throwaway names (e.g. `http-test-<random>`)
and clean up by name only.

## Running it

```sh
nix run                              # build + run, port 8765
nix run . -- --port 8766             # alternate port
nix develop -c python3 server.py     # dev shell
```

OpenAPI spec is at `/openapi.json`; Swagger UI at `/docs`.

## Code shape

- `server.py` — everything: app, models, route handlers, `main()`. Keep it
  this way unless there's a real reason to split.
- Helpers `_bool`, `_int`, `session_dict`, `window_dict`, `pane_dict` exist
  because libtmux returns string-typed attributes — use them when adding
  new fields rather than parsing inline.
- `resolve_pane()` accepts both `%id` and `session:window.pane` forms; reuse
  it for any new pane endpoint.

## Conventions

- Errors are `HTTPException` with a 4xx code and a short message; no custom
  exception classes.
- Don't add backwards-compat shims, feature flags, or speculative
  abstractions. The whole point of this project is that it's small.
- Don't add comments that restate what the code does.

## Files

- `server.py` — the service
- `flake.nix` / `flake.lock` — Nix packaging (devShell + runnable package)
- `README.md` — user-facing docs
- `CONTRIBUTING.md` — contributor docs
- `LICENSE` — MIT


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:b380caf6 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues are stored as flat JSON files in `.beads/issues/`, tracked by git. Sync is via standard git operations.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits or git pushes unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
