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
