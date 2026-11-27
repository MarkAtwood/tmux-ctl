# tmux-ctl

REST API for tmux automation and AI agents. Full control over sessions, windows, 
panes, plus terminal state access for screen scraping and TUI automation.

Built on [libtmux] + [FastAPI].

[libtmux]: https://github.com/tmux-python/libtmux
[FastAPI]: https://fastapi.tiangolo.com/

## Install & run

Requires Nix with flakes enabled.

```sh
nix run                              # build and run on 127.0.0.1:8765
nix run . -- --host 0.0.0.0 --port 9000
nix develop -c python3 server.py     # dev shell
```

The server connects to your **default** tmux socket.

## API

OpenAPI spec at `/openapi.json`, Swagger UI at `/docs`.

### Sessions, Windows, Panes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List all sessions |
| POST | `/sessions` | Create session `{name, command?, width?, height?}` |
| GET | `/sessions/{name}` | Session detail with windows |
| DELETE | `/sessions/{name}` | Kill session |
| POST | `/sessions/{name}/rename` | Rename `{new_name}` |
| POST | `/sessions/{name}/windows` | Create window `{name?, command?}` |
| GET | `/windows` | List all windows |
| GET | `/windows/{target}` | Window detail with panes |
| DELETE | `/windows/{target}` | Kill window |
| POST | `/windows/{target}/split` | Split `{vertical?, command?, size?}` |
| GET | `/panes` | List all panes |
| GET | `/panes/{target}` | Pane detail |
| DELETE | `/panes/{target}` | Kill pane |
| POST | `/panes/{target}/split` | Split pane |
| POST | `/panes/{target}/resize` | Resize `{width?, height?, adjust?, direction?}` |

Targets: `@id` or `session:idx` for windows, `%id` or `session:window.pane` for panes.

### Input & Output

| Method | Path | Description |
|--------|------|-------------|
| GET | `/panes/{target}/output` | Capture text `?lines=N` |
| POST | `/panes/{target}/input` | Send keys `{keys, literal?, enter?}` |
| POST | `/panes/{target}/mouse` | Mouse event `{x, y, button, action}` |
| POST | `/panes/{target}/capture` | Capture region `{start_line, end_line, start_col, end_col}` |
| GET | `/panes/{target}/search` | Regex search `?pattern=X` |
| POST | `/panes/{target}/wait` | Wait for pattern `{pattern, timeout, interval}` |

### Terminal State (for TUI automation)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/panes/{target}/terminal` | Emulator state: modes, scroll region, tabs |
| GET | `/panes/{target}/screen` | Full screen capture, `?colors=true` for ANSI |
| GET | `/panes/{target}/grid` | Cell-level data: char, fg, bg, attrs |
| GET | `/panes/{target}/lines` | Lines with flags (prompt/output markers) |
| GET | `/panes/{target}/widgets` | Detect box-drawing UI regions (curses apps) |
| GET | `/panes/{target}/prompt` | Detect shell prompt (teletype mode) |

### Buffers, Clients, Options

| Method | Path | Description |
|--------|------|-------------|
| GET | `/buffers` | List paste buffers |
| GET/POST/DELETE | `/buffers/{name}` | Buffer CRUD |
| GET | `/clients` | List attached clients |
| GET/PUT | `/sessions/{name}/options/{opt}` | Session options |
| GET/PUT | `/windows/{target}/options/{opt}` | Window options |
| GET/PUT | `/panes/{target}/options/{opt}` | Pane options |
| GET/PUT/DELETE | `/sessions/{name}/env/{var}` | Session environment |

## Safety

Operations affect your real tmux sessions. Bind to `127.0.0.1` (default) unless
you have a reason not to.

## License

MIT
