"""tmux HTTP server — REST API over tmux."""

from __future__ import annotations

import argparse
import json
import re
from typing import Optional, List

import libtmux
from libtmux.constants import PaneDirection, ResizeAdjustmentDirection
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(title="tmux-ctl", description="REST API over tmux")
server = libtmux.Server()


def _bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v) == "1"


def _int(v, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def session_dict(s) -> dict:
    name = s.session_name
    return {
        "@type": "Session",
        "@id": f"/sessions/{name}",
        "name": name,
        "id": s.session_id,
        "created": _int(s.session_created),
        "attached": _bool(s.session_attached),
        "window_count": _int(getattr(s, "session_windows", None)),
        "grouped": _bool(getattr(s, "session_grouped", False)),
        "group": getattr(s, "session_group", None),
        "activity": _int(getattr(s, "session_activity", None)),
        "last_attached": _int(getattr(s, "session_last_attached", None)),
        "path": getattr(s, "session_path", None),
        "windows": f"/sessions/{name}/windows",
        "options": f"/sessions/{name}/options",
        "env": f"/sessions/{name}/env",
    }


def _parse_layout(layout_str):
    if not layout_str:
        return None
    try:
        return json.loads(layout_str)
    except (json.JSONDecodeError, TypeError):
        return layout_str  # return raw if not JSON


def window_dict(w) -> dict:
    wid = w.window_id
    return {
        "@type": "Window",
        "@id": f"/windows/{wid}",
        "index": _int(w.window_index),
        "id": wid,
        "name": w.window_name,
        "active": _bool(w.window_active),
        "pane_count": _int(w.window_panes),
        "layout": _parse_layout(getattr(w, "window_layout", None)),
        "width": _int(getattr(w, "window_width", None)),
        "height": _int(getattr(w, "window_height", None)),
        "flags": getattr(w, "window_flags", None),
        "activity": _int(getattr(w, "window_activity", None)),
        "options": f"/windows/{wid}/options",
        "split": f"/windows/{wid}/split",
    }


def pane_dict(p) -> dict:
    pid = p.pane_id
    return {
        "@type": "Pane",
        "@id": f"/panes/{pid}",
        "index": _int(p.pane_index),
        "id": pid,
        "active": _bool(p.pane_active),
        "pid": _int(p.pane_pid),
        "command": p.pane_current_command,
        "width": _int(p.pane_width),
        "height": _int(p.pane_height),
        "cursor_x": _int(getattr(p, "cursor_x", None)),
        "cursor_y": _int(getattr(p, "cursor_y", None)),
        "scroll_position": _int(getattr(p, "scroll_position", None)),
        "in_mode": _bool(getattr(p, "pane_in_mode", False)),
        "mode": getattr(p, "pane_mode", None),
        "tty": getattr(p, "pane_tty", None),
        "title": getattr(p, "pane_title", None),
        "path": getattr(p, "pane_current_path", None),
        "dead": _bool(getattr(p, "pane_dead", False)),
        "history_size": _int(getattr(p, "history_size", None)),
        "alternate_on": _bool(getattr(p, "alternate_on", False)),
        "cursor_visible": _bool(getattr(p, "cursor_flag", True)),
        "unseen_changes": _bool(getattr(p, "pane_unseen_changes", False)),
        "output": f"/panes/{pid}/output",
        "input": f"/panes/{pid}/input",
        "screen": f"/panes/{pid}/screen",
        "terminal": f"/panes/{pid}/terminal",
        "options": f"/panes/{pid}/options",
    }


def pane_terminal_state(pane_id: str) -> dict:
    """Get terminal emulator state via tmux format variables."""
    fmt = (
        "#{origin_flag}\t#{insert_flag}\t#{keypad_cursor_flag}\t"
        "#{wrap_flag}\t#{mouse_any_flag}\t#{mouse_button_flag}\t"
        "#{mouse_sgr_flag}\t#{scroll_region_upper}\t#{scroll_region_lower}\t"
        "#{pane_tabs}\t#{cursor_character}"
    )
    out = server.cmd("display-message", "-t", pane_id, "-p", fmt).stdout
    if isinstance(out, list):
        out = out[0] if out else ""
    parts = out.split("\t")
    if len(parts) < 11:
        parts.extend([""] * (11 - len(parts)))
    return {
        "origin_mode": _bool(parts[0]),
        "insert_mode": _bool(parts[1]),
        "application_cursor": _bool(parts[2]),
        "autowrap": _bool(parts[3]),
        "mouse_any": _bool(parts[4]),
        "mouse_button": _bool(parts[5]),
        "mouse_sgr": _bool(parts[6]),
        "scroll_region": [_int(parts[7]), _int(parts[8])],
        "tab_stops": [_int(x) for x in parts[9].split(",") if x],
        "cursor_char": parts[10] if parts[10] else " ",
    }


def get_session(name: str):
    matches = server.sessions.filter(session_name=name)
    if not matches:
        raise HTTPException(404, f"session {name!r} not found")
    return matches[0]


def get_window(session_name: str, idx: int):
    sess = get_session(session_name)
    wins = sess.windows.filter(window_index=str(idx))
    if not wins:
        raise HTTPException(404, f"window {idx} not found in session {session_name!r}")
    return wins[0]


def resolve_window(target: str):
    """Resolve `@id` or `session:window_index` to a libtmux Window."""
    if target.startswith("@"):
        matches = server.windows.filter(window_id=target)
        if not matches:
            raise HTTPException(404, f"window {target!r} not found")
        return matches[0]
    try:
        s_name, w_idx = target.split(":", 1)
    except ValueError:
        raise HTTPException(400, f"invalid window target: {target!r}")
    return get_window(s_name, int(w_idx))


def resolve_pane(target: str):
    """Resolve `%id` or `session:window.pane` to a libtmux Pane."""
    if target.startswith("%"):
        matches = server.panes.filter(pane_id=target)
        if not matches:
            raise HTTPException(404, f"pane {target!r} not found")
        return matches[0]
    try:
        if "." in target:
            sw, p_idx = target.rsplit(".", 1)
        else:
            sw, p_idx = target, "0"
        s_name, w_idx = sw.split(":", 1)
    except ValueError:
        raise HTTPException(400, f"invalid pane target: {target!r}")
    sess = get_session(s_name)
    wins = sess.windows.filter(window_index=str(w_idx))
    if not wins:
        raise HTTPException(404, f"window {w_idx} not found in session {s_name!r}")
    panes = wins[0].panes.filter(pane_index=str(p_idx))
    if not panes:
        raise HTTPException(404, f"pane {p_idx} not found in {s_name}:{w_idx}")
    return panes[0]


# Request models

class CreateSession(BaseModel):
    name: str
    command: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class CreateWindow(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None


class SplitPane(BaseModel):
    vertical: bool = True
    command: Optional[str] = None
    size: Optional[int] = None  # percentage


class ResizePane(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None
    adjust: Optional[str] = None  # e.g. "+5" or "-3"
    direction: Optional[str] = None  # U/D/L/R for adjust


class SendInput(BaseModel):
    keys: str
    literal: bool = False
    enter: bool = False


class MouseEvent(BaseModel):
    x: int
    y: int
    button: int = 1  # 1=left, 2=middle, 3=right
    action: str = "click"  # click, press, release, move, scroll_up, scroll_down


class CaptureArea(BaseModel):
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_col: Optional[int] = None
    end_col: Optional[int] = None


class Rename(BaseModel):
    new_name: str

    def model_post_init(self, __context):
        if not self.new_name.strip():
            raise ValueError("new_name cannot be empty")


class SetOption(BaseModel):
    value: str


def buffer_dict(b) -> dict:
    return {
        "name": b.get("buffer_name"),
        "size": _int(b.get("buffer_size")),
        "created": _int(b.get("buffer_created")),
    }


def client_dict(c) -> dict:
    return {
        "name": c.get("client_name"),
        "tty": c.get("client_tty"),
        "session": c.get("client_session"),
        "width": _int(c.get("client_width")),
        "height": _int(c.get("client_height")),
        "created": _int(c.get("client_created")),
        "activity": _int(c.get("client_activity")),
        "pid": _int(c.get("client_pid")),
        "utf8": _bool(c.get("client_utf8", False)),
        "readonly": _bool(c.get("client_readonly", False)),
    }


# Root

@app.get("/")
def root():
    return {
        "@type": "ServiceRoot",
        "@id": "/",
        "name": "tmux-ctl",
        "sessions": "/sessions",
        "windows": "/windows",
        "panes": "/panes",
        "buffers": "/buffers",
        "clients": "/clients",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# Buffers

@app.get("/buffers")
def buffers_list():
    out = server.cmd("list-buffers", "-F",
        "#{buffer_name}\t#{buffer_size}\t#{buffer_created}").stdout
    buffers = []
    for line in out:
        parts = line.split("\t")
        if len(parts) >= 3:
            buffers.append({
                "name": parts[0],
                "size": _int(parts[1]),
                "created": _int(parts[2]),
            })
    return buffers


@app.get("/buffers/{name}")
def buffer_get(name: str):
    try:
        out = server.cmd("show-buffer", "-b", name).stdout
    except Exception:
        raise HTTPException(404, f"buffer {name!r} not found")
    content = "\n".join(out) if isinstance(out, list) else out
    return {"name": name, "content": content}


class CreateBuffer(BaseModel):
    content: str
    name: Optional[str] = None


@app.post("/buffers", status_code=201)
def buffer_create(body: CreateBuffer):
    if body.name:
        server.cmd("set-buffer", "-b", body.name, body.content)
    else:
        server.cmd("set-buffer", body.content)
    return {"ok": True, "name": body.name}


@app.delete("/buffers/{name}")
def buffer_delete(name: str):
    try:
        server.cmd("delete-buffer", "-b", name)
    except Exception:
        raise HTTPException(404, f"buffer {name!r} not found")
    return {"ok": True}


# Clients

@app.get("/clients")
def clients_list():
    out = server.cmd("list-clients", "-F",
        "#{client_name}\t#{client_tty}\t#{client_session}\t#{client_width}\t"
        "#{client_height}\t#{client_created}\t#{client_activity}\t#{client_pid}\t"
        "#{client_utf8}\t#{client_readonly}").stdout
    clients = []
    for line in out:
        parts = line.split("\t")
        if len(parts) >= 10:
            clients.append({
                "name": parts[0],
                "tty": parts[1],
                "session": parts[2],
                "width": _int(parts[3]),
                "height": _int(parts[4]),
                "created": _int(parts[5]),
                "activity": _int(parts[6]),
                "pid": _int(parts[7]),
                "utf8": _bool(parts[8]),
                "readonly": _bool(parts[9]),
            })
    return clients


@app.get("/clients/{tty:path}")
def client_get(tty: str):
    if not tty.startswith("/"):
        tty = "/" + tty
    clients = clients_list()
    for c in clients:
        if c["tty"] == tty:
            return c
    raise HTTPException(404, f"client {tty!r} not found")


# Sessions

@app.get("/sessions")
def sessions_list():
    return [session_dict(s) for s in server.sessions]


@app.post("/sessions", status_code=201)
def sessions_create(body: CreateSession):
    if server.sessions.filter(session_name=body.name):
        raise HTTPException(409, f"session {body.name!r} exists")
    kwargs: dict = {"session_name": body.name}
    if body.command:
        kwargs["window_command"] = body.command
    if body.width:
        kwargs["x"] = body.width
    if body.height:
        kwargs["y"] = body.height
    s = server.new_session(**kwargs)
    return session_dict(s)


@app.get("/sessions/{name}")
def session_get(name: str):
    s = get_session(name)
    return {**session_dict(s), "windows": [window_dict(w) for w in s.windows]}


@app.delete("/sessions/{name}")
def session_delete(name: str):
    s = get_session(name)
    s.kill()
    return {"ok": True}


@app.post("/sessions/{name}/rename")
def session_rename(name: str, body: Rename):
    s = get_session(name)
    if body.new_name == name:
        return session_dict(s)  # no-op
    existing = server.sessions.filter(session_name=body.new_name)
    if existing:
        raise HTTPException(409, f"session {body.new_name!r} already exists")
    try:
        s.rename_session(body.new_name)
    except Exception:
        # TOCTOU: another client created the name between check and rename
        raise HTTPException(409, f"session {body.new_name!r} already exists")
    return session_dict(s)


@app.get("/sessions/{name}/windows")
def session_windows(name: str):
    s = get_session(name)
    return [window_dict(w) for w in s.windows]


@app.post("/sessions/{name}/windows", status_code=201)
def session_create_window(name: str, body: CreateWindow):
    s = get_session(name)
    kwargs = {}
    if body.name:
        kwargs["window_name"] = body.name
    if body.command:
        kwargs["window_command"] = body.command
    w = s.new_window(**kwargs)
    return window_dict(w)


@app.get("/sessions/{name}/options")
def session_options_list(name: str, inherited: bool = True):
    s = get_session(name)
    return s.show_options(include_inherited=inherited)


@app.get("/sessions/{name}/options/{option}")
def session_option_get(name: str, option: str):
    s = get_session(name)
    opts = s.show_options(include_inherited=True)
    if option not in opts:
        raise HTTPException(404, f"option {option!r} not found")
    return {"option": option, "value": opts[option]}


@app.put("/sessions/{name}/options/{option}")
def session_option_set(name: str, option: str, body: SetOption):
    s = get_session(name)
    s.set_option(option, body.value)
    return {"option": option, "value": body.value}


@app.get("/sessions/{name}/env")
def session_env_list(name: str):
    s = get_session(name)
    return s.show_environment()


@app.get("/sessions/{name}/env/{var}")
def session_env_get(name: str, var: str):
    s = get_session(name)
    env = s.show_environment()
    if var not in env:
        raise HTTPException(404, f"env var {var!r} not found")
    return {"var": var, "value": env[var]}


@app.put("/sessions/{name}/env/{var}")
def session_env_set(name: str, var: str, body: SetOption):
    s = get_session(name)
    s.set_environment(var, body.value)
    return {"var": var, "value": body.value}


@app.delete("/sessions/{name}/env/{var}")
def session_env_unset(name: str, var: str):
    s = get_session(name)
    s.unset_environment(var)
    return {"ok": True}


# Windows

@app.get("/windows")
def windows_list():
    return [window_dict(w) for w in server.windows]


@app.get("/windows/{target}")
def window_get(target: str):
    w = resolve_window(target)
    return {**window_dict(w), "panes": [pane_dict(p) for p in w.panes]}


@app.delete("/windows/{target}")
def window_delete(target: str):
    w = resolve_window(target)
    w.kill()
    return {"ok": True}


@app.post("/windows/{target}/rename")
def window_rename(target: str, body: Rename):
    w = resolve_window(target)
    w.rename_window(body.new_name)
    return window_dict(w)


@app.post("/windows/{target}/split", status_code=201)
def window_split(target: str, body: SplitPane):
    w = resolve_window(target)
    direction = PaneDirection.Right if body.vertical else PaneDirection.Below
    kwargs = {"direction": direction}
    if body.command:
        kwargs["shell"] = body.command
    if body.size:
        kwargs["percentage"] = body.size
    p = w.split(**kwargs)
    return pane_dict(p)


@app.get("/windows/{target}/options")
def window_options_list(target: str, inherited: bool = True):
    w = resolve_window(target)
    return w.show_options(include_inherited=inherited)


@app.get("/windows/{target}/options/{option}")
def window_option_get(target: str, option: str):
    w = resolve_window(target)
    opts = w.show_options(include_inherited=True)
    if option not in opts:
        raise HTTPException(404, f"option {option!r} not found")
    return {"option": option, "value": opts[option]}


@app.put("/windows/{target}/options/{option}")
def window_option_set(target: str, option: str, body: SetOption):
    w = resolve_window(target)
    w.set_option(option, body.value)
    return {"option": option, "value": body.value}


# Panes

@app.get("/panes")
def panes_list():
    return [pane_dict(p) for p in server.panes]


@app.get("/panes/{target}")
def pane_get(target: str):
    p = resolve_pane(target)
    return pane_dict(p)


@app.delete("/panes/{target}")
def pane_delete(target: str):
    p = resolve_pane(target)
    p.kill()
    return {"ok": True}


@app.get("/panes/{target}/output")
def pane_output(target: str, lines: int = 100):
    pane = resolve_pane(target)
    out = pane.capture_pane(start=-lines)
    if isinstance(out, list):
        out = "\n".join(out)
    return {"target": target, "output": out}


@app.post("/panes/{target}/input")
def pane_input(target: str, body: SendInput):
    pane = resolve_pane(target)
    pane.send_keys(body.keys, literal=body.literal, enter=body.enter)
    return {"ok": True}


@app.post("/panes/{target}/mouse")
def pane_mouse(target: str, body: MouseEvent):
    pane = resolve_pane(target)
    # ponytail: tmux mouse via escape sequences, upgrade to libtmux mouse API if added
    btn_code = {1: 0, 2: 1, 3: 2}.get(body.button, 0)
    if body.action == "scroll_up":
        btn_code = 64
    elif body.action == "scroll_down":
        btn_code = 65
    elif body.action == "move":
        btn_code = 32 + btn_code
    elif body.action == "release":
        btn_code = 3
    cx, cy = body.x + 33, body.y + 33
    if body.action in ("click", "press"):
        seq = f"\x1b[M{chr(btn_code + 32)}{chr(cx)}{chr(cy)}"
        pane.send_keys(seq, literal=True)
        if body.action == "click":
            seq_up = f"\x1b[M{chr(3 + 32)}{chr(cx)}{chr(cy)}"
            pane.send_keys(seq_up, literal=True)
    else:
        seq = f"\x1b[M{chr(btn_code + 32)}{chr(cx)}{chr(cy)}"
        pane.send_keys(seq, literal=True)
    return {"ok": True}


@app.post("/panes/{target}/capture")
def pane_capture(target: str, body: CaptureArea):
    pane = resolve_pane(target)
    start = body.start_line if body.start_line is not None else 0
    end = body.end_line if body.end_line is not None else -1
    lines = pane.capture_pane(start=start, end=end)
    if isinstance(lines, str):
        lines = lines.split("\n")
    if body.start_col is not None or body.end_col is not None:
        sc = body.start_col or 0
        ec = body.end_col
        lines = [line[sc:ec] for line in lines]
    return {"lines": lines}


@app.get("/panes/{target}/search")
def pane_search(target: str, pattern: str, lines: int = 1000):
    pane = resolve_pane(target)
    out = pane.capture_pane(start=-lines)
    if isinstance(out, list):
        out = "\n".join(out)
    matches: List[dict] = []
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise HTTPException(400, f"invalid regex: {e}")
    for i, line in enumerate(out.split("\n")):
        for m in regex.finditer(line):
            matches.append({"line": i, "start": m.start(), "end": m.end(), "match": m.group()})
    return {"pattern": pattern, "matches": matches}


@app.post("/panes/{target}/split", status_code=201)
def pane_split(target: str, body: SplitPane):
    p = resolve_pane(target)
    direction = PaneDirection.Right if body.vertical else PaneDirection.Below
    kwargs = {"direction": direction}
    if body.command:
        kwargs["shell"] = body.command
    if body.size:
        kwargs["percentage"] = body.size
    new_pane = p.split(**kwargs)
    return pane_dict(new_pane)


@app.post("/panes/{target}/resize")
def pane_resize(target: str, body: ResizePane):
    p = resolve_pane(target)
    if body.width is not None or body.height is not None:
        p.resize(width=body.width, height=body.height)
    if body.adjust and body.direction:
        dir_map = {"U": ResizeAdjustmentDirection.Up, "D": ResizeAdjustmentDirection.Down,
                   "L": ResizeAdjustmentDirection.Left, "R": ResizeAdjustmentDirection.Right}
        adj_dir = dir_map.get(body.direction.upper()[0])
        if adj_dir:
            p.resize(adjustment_direction=adj_dir, adjustment=abs(int(body.adjust)))
    return pane_dict(p)


@app.get("/panes/{target}/options")
def pane_options_list(target: str, inherited: bool = True):
    p = resolve_pane(target)
    return p.show_options(include_inherited=inherited)


@app.get("/panes/{target}/options/{option}")
def pane_option_get(target: str, option: str):
    p = resolve_pane(target)
    opts = p.show_options(include_inherited=True)
    if option not in opts:
        raise HTTPException(404, f"option {option!r} not found")
    return {"option": option, "value": opts[option]}


@app.put("/panes/{target}/options/{option}")
def pane_option_set(target: str, option: str, body: SetOption):
    p = resolve_pane(target)
    p.set_option(option, body.value)
    return {"option": option, "value": body.value}


# Terminal state and grid access

@app.get("/panes/{target}/terminal")
def pane_terminal(target: str):
    """Get terminal emulator state (modes, scroll region, tabs)."""
    pane = resolve_pane(target)
    return pane_terminal_state(pane.pane_id)


@app.get("/panes/{target}/grid")
def pane_grid(target: str, start: int = 0, end: int = -1):
    """Get cell-level grid data with character, colors, and attributes."""
    pane = resolve_pane(target)
    args = ["capture-pane", "-t", pane.pane_id, "-p", "-R"]
    if start != 0:
        args.extend(["-S", str(start)])
    if end != -1:
        args.extend(["-E", str(end)])
    out = server.cmd(*args).stdout
    if isinstance(out, list):
        out = "\n".join(out)
    return {"grid": _parse_grid(out), "pane_id": pane.pane_id}


def _parse_grid(raw: str) -> dict:
    """Parse tmux capture-pane -R diagnostic output into structured data."""
    lines_data = []
    current_line = None
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("G "):
            # grid header: G 80x24 (0/2000)
            m = re.match(r"G (\d+)x(\d+)", line)
            if m:
                width, height = int(m.group(1)), int(m.group(2))
        elif line.startswith("L "):
            # line header: L 0 (0) flags=NONE[0] 0/0
            m = re.match(r"L (\d+) .* flags=(\w+)", line)
            if m:
                if current_line is not None:
                    lines_data.append(current_line)
                current_line = {"y": int(m.group(1)), "flags": m.group(2), "cells": []}
        elif line.startswith("C ") and current_line is not None:
            # cell: C 1,0 data=(1,1,T) flags=NONE[0] attr=BOLD[1] fg=colour196[1] bg=default[8]
            cell = _parse_cell(line)
            if cell:
                current_line["cells"].append(cell)
    if current_line is not None:
        lines_data.append(current_line)
    return {"lines": lines_data}


def _parse_cell(line: str) -> dict:
    """Parse a single cell line from -R output."""
    m = re.match(r"C (\d+),(\d+) data=\((\d+),(\d+),(.?)\)", line)
    if not m:
        return None
    y, x, _, _, char = m.groups()
    cell = {"x": int(x), "y": int(y), "char": char if char else " "}
    # extract attributes
    if "attr=" in line:
        attr_m = re.search(r"attr=(\w+)", line)
        if attr_m and attr_m.group(1) != "NONE":
            cell["attr"] = attr_m.group(1)
    if "fg=" in line:
        fg_m = re.search(r"fg=(\w+)", line)
        if fg_m and fg_m.group(1) != "default":
            cell["fg"] = fg_m.group(1)
    if "bg=" in line:
        bg_m = re.search(r"bg=(\w+)", line)
        if bg_m and bg_m.group(1) != "default":
            cell["bg"] = bg_m.group(1)
    return cell


@app.get("/panes/{target}/lines")
def pane_lines(target: str, start: int = 0, end: int = -1):
    """Get line-level data with flags (prompt markers, etc)."""
    pane = resolve_pane(target)
    args = ["capture-pane", "-t", pane.pane_id, "-p", "-F", "-L"]
    if start != 0:
        args.extend(["-S", str(start)])
    if end != -1:
        args.extend(["-E", str(end)])
    out = server.cmd(*args).stdout
    if isinstance(out, list):
        lines = out
    else:
        lines = out.split("\n")
    result = []
    for line in lines:
        m = re.match(r"(\d+) ([-DOPXH]+) (.*)", line)
        if m:
            lineno, flags, text = m.groups()
            result.append({
                "line": int(lineno),
                "flags": flags if flags != "-" else None,
                "prompt": "P" in flags,  # shell integration prompt marker
                "output": "O" in flags,  # shell integration output marker
                "text": text,
            })
    return {"lines": result}


@app.get("/panes/{target}/commands")
def pane_commands(target: str, limit: int = 50):
    """Get shell commands with their output, parsed from OSC 133 markers."""
    pane = resolve_pane(target)
    out = server.cmd("capture-pane", "-t", pane.pane_id, "-p", "-F", "-L", "-S", "-").stdout
    if isinstance(out, list):
        lines = out
    else:
        lines = out.split("\n")

    commands = []
    current_cmd = None

    for line in lines:
        m = re.match(r"(\d+) ([-DOPXHW]+) (.*)", line)
        if not m:
            continue
        lineno, flags, text = m.groups()
        lineno = int(lineno)

        if "P" in flags:
            # prompt line - start of new command
            if current_cmd is not None:
                commands.append(current_cmd)
            current_cmd = {
                "prompt_line": lineno,
                "prompt": text,
                "command": None,  # extracted from prompt text
                "output_start": None,
                "output_end": None,
                "output": [],
            }
            # try to extract command from prompt (after $ or > or #)
            cmd_m = re.search(r"[$#>]\s*(.+)$", text)
            if cmd_m:
                current_cmd["command"] = cmd_m.group(1).strip()
        elif "O" in flags and current_cmd is not None:
            # output line
            if current_cmd["output_start"] is None:
                current_cmd["output_start"] = lineno
            current_cmd["output_end"] = lineno
            current_cmd["output"].append(text)

    if current_cmd is not None:
        commands.append(current_cmd)

    # return most recent N commands
    return {
        "@type": "CommandHistory",
        "@id": f"/panes/{pane.pane_id}/commands",
        "commands": commands[-limit:] if limit else commands,
    }


# Mode-aware terminal access

@app.get("/panes/{target}/screen")
def pane_screen(target: str, colors: bool = False):
    """Capture visible screen. With colors=true, includes ANSI escape sequences."""
    pane = resolve_pane(target)
    if colors:
        # capture with escape sequences for colors/attributes
        out = server.cmd("capture-pane", "-t", pane.pane_id, "-e", "-p").stdout
    else:
        out = pane.capture_pane()
    if isinstance(out, list):
        out = "\n".join(out)
    info = pane_dict(pane)
    return {
        "screen": out,
        "width": info["width"],
        "height": info["height"],
        "cursor_x": info["cursor_x"],
        "cursor_y": info["cursor_y"],
        "alternate_on": info["alternate_on"],
    }


class WaitFor(BaseModel):
    pattern: str
    timeout: float = 5.0
    interval: float = 0.1
    lines: int = 100


@app.post("/panes/{target}/wait")
def pane_wait(target: str, body: WaitFor):
    """Wait for pattern to appear in pane output. Returns match or times out."""
    import time
    pane = resolve_pane(target)
    try:
        regex = re.compile(body.pattern)
    except re.error as e:
        raise HTTPException(400, f"invalid regex: {e}")
    deadline = time.time() + body.timeout
    while time.time() < deadline:
        out = pane.capture_pane(start=-body.lines)
        if isinstance(out, list):
            out = "\n".join(out)
        m = regex.search(out)
        if m:
            return {"found": True, "match": m.group(), "start": m.start(), "end": m.end()}
        time.sleep(body.interval)
    return {"found": False, "match": None}


BOX_CHARS = set("─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬━┃┏┓┗┛┣┫┳┻╋")


@app.get("/panes/{target}/widgets")
def pane_widgets(target: str):
    """Detect UI widgets in curses-mode panes by finding box-drawing regions."""
    pane = resolve_pane(target)
    out = pane.capture_pane()
    if isinstance(out, list):
        lines = out
    else:
        lines = out.split("\n")
    # ponytail: simple box detection - finds rectangular regions bounded by box chars
    # upgrade to full ncurses widget detection if needed
    boxes = []
    h = len(lines)
    w = max((len(line) for line in lines), default=0)
    # find top-left corners
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch in "┌╔┏" and _is_box_corner(lines, x, y, w, h):
                box = _trace_box(lines, x, y, w, h)
                if box:
                    boxes.append(box)
    return {
        "alternate_on": _bool(getattr(pane, "alternate_on", False)),
        "widgets": boxes,
    }


def _is_box_corner(lines, x, y, w, h):
    """Check if position looks like top-left of a box."""
    if y + 1 >= h:
        return False
    line = lines[y]
    next_line = lines[y + 1] if y + 1 < len(lines) else ""
    # check right for horizontal line
    if x + 1 < len(line) and line[x + 1] in "─═━":
        # check down for vertical line
        if x < len(next_line) and next_line[x] in "│║┃":
            return True
    return False


def _trace_box(lines, start_x, start_y, w, h):
    """Trace a box from top-left corner, return bounds and label."""
    # find right edge
    line = lines[start_y]
    end_x = start_x + 1
    while end_x < len(line) and line[end_x] in "─═━":
        end_x += 1
    if end_x >= len(line) or line[end_x] not in "┐╗┓":
        return None
    # find bottom edge
    end_y = start_y + 1
    while end_y < len(lines):
        if start_x >= len(lines[end_y]):
            break
        ch = lines[end_y][start_x]
        if ch in "└╚┗":
            break
        if ch not in "│║┃":
            return None
        end_y += 1
    if end_y >= len(lines):
        return None
    # extract title (text between corners on top line)
    title_region = line[start_x + 1:end_x]
    title = title_region.strip("─═━ ")
    return {
        "x": start_x,
        "y": start_y,
        "width": end_x - start_x + 1,
        "height": end_y - start_y + 1,
        "title": title if title else None,
    }


PROMPT_PATTERNS = [
    r"^\s*[\$#>%]\s*$",  # common prompt endings
    r"^\s*\S+[@:][^$#>%]*[\$#>%]\s*$",  # user@host:path$
    r"^\(\S+\)\s*[\$#>%]\s*$",  # (venv) $
]


@app.get("/panes/{target}/prompt")
def pane_prompt(target: str):
    """Detect shell prompt in teletype-mode panes. Returns prompt line and whether shell is waiting."""
    pane = resolve_pane(target)
    info = pane_dict(pane)
    # if in alternate screen, not a teletype
    if info["alternate_on"]:
        return {"teletype": False, "prompt": None, "waiting": False}
    out = pane.capture_pane()
    if isinstance(out, list):
        lines = out
    else:
        lines = out.split("\n")
    # look for prompt at cursor line or last non-empty line
    cursor_y = info["cursor_y"]
    prompt_line = None
    prompt_y = None
    # check cursor line first
    if 0 <= cursor_y < len(lines):
        line = lines[cursor_y]
        if _looks_like_prompt(line):
            prompt_line = line
            prompt_y = cursor_y
    # fall back to last non-empty line
    if not prompt_line:
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                if _looks_like_prompt(lines[i]):
                    prompt_line = lines[i]
                    prompt_y = i
                break
    # shell is "waiting" if cursor is at end of prompt line
    waiting = False
    if prompt_line and prompt_y == cursor_y:
        # cursor at or near end of prompt
        waiting = info["cursor_x"] >= len(prompt_line.rstrip()) - 1
    return {
        "teletype": True,
        "prompt": prompt_line,
        "prompt_y": prompt_y,
        "waiting": waiting,
        "cursor_x": info["cursor_x"],
        "cursor_y": info["cursor_y"],
    }


def _looks_like_prompt(line: str) -> bool:
    """Heuristic: does this line look like a shell prompt?"""
    line = line.rstrip()
    if not line:
        return False
    for pat in PROMPT_PATTERNS:
        if re.search(pat, line):
            return True
    # also check if ends with common prompt chars and is short-ish
    if len(line) < 80 and line.rstrip()[-1:] in "$#>%":
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
