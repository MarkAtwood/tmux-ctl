# Contributing

Thanks for your interest in tmux-ctl.

## Dev environment

```sh
nix develop                  # drops you into a shell with python+deps+tmux
python3 server.py            # iterate
```

Or, without entering the shell:

```sh
nix develop -c python3 server.py
```

## Trying changes

The server connects to your default tmux. To test without disturbing real
work, use a separate tmux server with a named socket:

```sh
tmux -L dev new-session -d -s scratch
TMUX_SOCKET=dev nix develop -c python3 server.py   # see note below
```

Currently the server always uses the default socket; if you want to make this
configurable, that's a perfectly good first PR — add a `--socket` flag and
pass it through to `libtmux.Server(socket_name=...)`.

## Pull requests

- Keep changes minimal and focused. One concern per PR.
- Match the existing style — no new abstractions unless they pull weight.
- Update the README endpoint table if you add or change an endpoint.
- Don't add comments that just restate what the code does.

## Reporting issues

Include: OS, tmux version (`tmux -V`), Python version, the exact request you
made, and what happened vs. what you expected. A minimal reproducer is
worth a thousand words.

## Code of conduct

Be kind. Assume good faith.
