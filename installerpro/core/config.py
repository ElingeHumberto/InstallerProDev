import json, pathlib

_CFG = pathlib.Path.home() / ".installerpro.cfg"

def get_default_path() -> str | None:
    if _CFG.exists():
        return json.loads(_CFG.read_text()).get("default_path")
    return None

def set_default_path(path: str) -> None:
    _CFG.write_text(json.dumps({"default_path": path}))
