"""
Lightweight JSON-file persistence. No DB in V1 -- the whole point is that a
single user can `cat data/pipeline.json` and understand their own state.
"""
import json
import os
import datetime

from . import config


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _path(name: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    return os.path.join(config.DATA_DIR, name)


def load(name: str, default):
    p = _path(name)
    if not os.path.exists(p):
        return default
    with open(p, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Corrupt file shouldn't crash the whole app -- back it up and
            # start fresh, but tell the user loudly.
            backup = p + ".corrupt." + now_iso().replace(":", "-")
            os.rename(p, backup)
            print(f"[warn] {name} was corrupt JSON. Backed up to {backup}.")
            return default


def save(name: str, data) -> None:
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, p)  # atomic write, avoids partial-file corruption


def save_markdown_report(agent_name: str, content: str) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    ts = now_iso().replace(":", "-")
    path = os.path.join(config.OUTPUT_DIR, f"{agent_name}_{ts}.md")
    with open(path, "w") as f:
        f.write(content)
    return path
