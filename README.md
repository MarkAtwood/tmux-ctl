# tmux-api

HTTP API for tmux. Control sessions, windows, panes. Read terminal state.

## Install

```sh
pip install tmux-api
```

Or isolated:

```sh
pipx install tmux-api
```

Or via Homebrew:

```sh
brew install MarkAtwood/tap/tmux-api
```

Requires tmux.

## Run

```sh
tmux-api                    # 127.0.0.1:8765
tmux-api --port 9000        # custom port
tmux-api --host 0.0.0.0     # all interfaces
```

Connects to your default tmux socket.

## API

Swagger UI at `/docs`. OpenAPI spec at `/openapi.json`.

Targets: windows take `@id` or `session:index`, panes take `%id` or `session:window.pane`.

### Sessions

```
GET    /sessions
POST   /sessions              {name, command?, width?, height?}
GET    /sessions/{name}
DELETE /sessions/{name}
POST   /sessions/{name}/rename {new_name}
POST   /sessions/{name}/windows {name?, command?}
```

### Windows

```
GET    /windows
GET    /windows/{target}
DELETE /windows/{target}
POST   /windows/{target}/rename {new_name}
POST   /windows/{target}/split  {vertical?, command?, size?}
```

### Panes

```
GET    /panes
GET    /panes/{target}
DELETE /panes/{target}
POST   /panes/{target}/split   {vertical?, command?, size?}
POST   /panes/{target}/resize  {width?, height?}
```

### I/O

```
GET    /panes/{target}/output  ?lines=100
POST   /panes/{target}/input   {keys, literal?, enter?}
POST   /panes/{target}/mouse   {x, y, button, action}
POST   /panes/{target}/capture {start_line?, end_line?, start_col?, end_col?}
GET    /panes/{target}/search  ?pattern=regex
POST   /panes/{target}/wait    {pattern, timeout?, interval?}
```

### Terminal State

```
GET    /panes/{target}/terminal   modes, scroll region, tabs
GET    /panes/{target}/screen     visible screen, ?colors=true for ANSI
GET    /panes/{target}/grid       cell-level: char, fg, bg, attrs
GET    /panes/{target}/lines      with prompt/output flags (OSC 133)
GET    /panes/{target}/commands   shell commands grouped with output
GET    /panes/{target}/widgets    box-drawing regions (curses apps)
GET    /panes/{target}/prompt     shell prompt detection
```

### Buffers, Clients, Options

```
GET    /buffers
GET    /buffers/{name}
POST   /buffers           {content, name?}
DELETE /buffers/{name}

GET    /clients

GET    /sessions/{name}/options
PUT    /sessions/{name}/options/{opt} {value}
GET    /sessions/{name}/env
PUT    /sessions/{name}/env/{var}     {value}
DELETE /sessions/{name}/env/{var}
```

Same pattern for `/windows/{target}/options` and `/panes/{target}/options`.

## Examples

```sh
# list sessions
curl localhost:8765/sessions

# create session
curl -X POST localhost:8765/sessions -H 'content-type: application/json' \
  -d '{"name":"work"}'

# send keys
curl -X POST localhost:8765/panes/work:0.0/input -H 'content-type: application/json' \
  -d '{"keys":"echo hello","enter":true}'

# read output
curl 'localhost:8765/panes/work:0.0/output?lines=10'

# wait for prompt
curl -X POST localhost:8765/panes/work:0.0/wait -H 'content-type: application/json' \
  -d '{"pattern":"\\$\\s*$","timeout":5}'

# kill session
curl -X DELETE localhost:8765/sessions/work
```

## Development

```sh
git clone https://github.com/MarkAtwood/tmux-ctl
cd tmux-ctl
pip install -e .
tmux-api
```

Nix users: `nix develop` for a shell, `nix run` to run directly.

## License

MIT
