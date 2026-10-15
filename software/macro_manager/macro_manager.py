"""Read and persist the visible file, macro, and action dashboard states."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote, unquote

CHECKBOX_RE = re.compile(r"\[\s*([01])\s*\]")
FILE_ROW_RE = re.compile(r"📂\s*(.+?)\s*(?:\(MASTER INCLUDE MAP\))?\s*$")
ACTION_ROW_RE = re.compile(r"⚙️\s*SYSTEM ACTION:\s*(.+?)\s*$", re.I)
MACRO_ROW_RE = re.compile(r"▶\s*(?:\[D[!?]\]\s*)?([A-Za-z0-9_.-]+)", re.I)
STATE_LINE_RE = re.compile(r"\[\s*([01])\s*\]")


def normalize_component_key(target_type: str, raw_name: str, scope: str | None = None) -> str:
    """Create a stable state key while retaining meaningful name characters.

    Macro keys may be scoped to the file that defines them (``macro_<name>@<file>``)
    so duplicate definitions in different files hold independent states.
    """
    name = raw_name.strip().lower()
    if target_type == "file":
        name = quote(name, safe="._-")
        if name.endswith(".cfg"):
            name = f"{name[:-4]}_cfg"
        elif name.endswith(".conf"):
            name = f"{name[:-5]}_conf"
    elif target_type == "macro":
        name = quote(name, safe="._-")
        if scope:
            name = f"{name}@{quote(scope.strip().lower(), safe='._-')}"
    elif target_type == "action":
        name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    else:
        raise ValueError(f"Unsupported dashboard target type: {target_type}")
    return f"{target_type}_{name}"


def decode_component_key(key: str) -> tuple[str, str]:
    """Return the target type and original target name represented by a key."""
    target_type, separator, name = key.partition("_")
    if not separator or target_type not in {"file", "macro", "action"}:
        raise ValueError(f"Invalid dashboard state key: {key}")
    if target_type == "file":
        if name.endswith("_cfg"):
            name = f"{name[:-4]}.cfg"
        elif name.endswith("_conf"):
            name = f"{name[:-5]}.conf"
    if target_type == "macro":
        name = name.partition("@")[0]
    return target_type, unquote(name)


def macro_key_scope(key: str) -> str | None:
    """Return the defining file (lowercase basename) of a scoped macro key, else None."""
    if not key.startswith("macro_") or "@" not in key:
        return None
    return unquote(key.partition("@")[2])


def parse_dashboard_line(line: str, file_scope: str | None = None) -> tuple[str, int] | None:
    """Parse one checkbox row into a unique state key and binary value.

    ``file_scope`` is the file section the row sits under; it scopes macro rows.
    """
    if line.lstrip().startswith("#"):
        return None
    checkbox = CHECKBOX_RE.search(line)
    if not checkbox:
        return None

    scope = None
    action = ACTION_ROW_RE.search(line)
    if action:
        target_type, raw_name = "action", action.group(1)
    else:
        file_row = FILE_ROW_RE.search(line)
        if file_row:
            target_type, raw_name = "file", file_row.group(1).strip()
        else:
            macro_row = MACRO_ROW_RE.search(line)
            if not macro_row:
                return None
            target_type, raw_name = "macro", macro_row.group(1)
            scope = file_scope

    return normalize_component_key(target_type, raw_name, scope), int(checkbox.group(1))


def iter_dashboard_rows(lines):
    """Yield (line, parsed) pairs, tracking the current file section for macro scoping."""
    file_scope = None
    for line in lines:
        parsed = parse_dashboard_line(line, file_scope)
        if parsed:
            target_type, name = decode_component_key(parsed[0])
            if target_type == "file":
                file_scope = name
            elif target_type == "action":
                file_scope = None
        yield line, parsed


class MacroManager:
    """State owner for the human-editable dashboard file."""

    def __init__(self, manager_path: Path):
        self.manager_path = Path(manager_path)
        self.states: dict[str, int] = {}
        self.load()

    def load(self) -> None:
        if not self.manager_path.exists():
            self.states = {}
            return
        if not self.manager_path.is_file():
            raise OSError(f"Dashboard path is not a file: {self.manager_path}")

        states: dict[str, int] = {}
        for _line, parsed in iter_dashboard_rows(self.manager_path.read_text(encoding="utf-8").splitlines()):
            if parsed:
                key, value = parsed
                states[key] = value
        self.states = states

    def get_state(self, name: str) -> int:
        return self.states.get(name, 0)

    def set_state(self, name: str, value: int | bool) -> None:
        if type(value) not in (int, bool) or value not in (0, 1):
            raise ValueError("Dashboard state must be binary 0 or 1")
        self.states[name] = int(value)

    def list_macros(self) -> list[str]:
        return list(self.states)

    def persist(self) -> None:
        """Update recognized checkbox values without regenerating dashboard text."""
        if not self.manager_path.is_file():
            raise FileNotFoundError(f"Dashboard does not exist: {self.manager_path}")

        original = self.manager_path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        found: set[str] = set()
        output: list[str] = []

        for line, parsed in iter_dashboard_rows(lines):
            if not parsed:
                output.append(line)
                continue

            key, _ = parsed
            if key not in self.states:
                output.append(line)
                continue
            found.add(key)
            new_value = self.states[key]
            output.append(
                STATE_LINE_RE.sub(
                    lambda match: match.group(0).replace(match.group(1), str(new_value), 1),
                    line,
                    count=1,
                )
            )

        missing = self.states.keys() - found
        if missing:
            raise KeyError(f"Dashboard rows not found for state keys: {', '.join(sorted(missing))}")

        updated = "".join(output)
        if updated != original:
            self.manager_path.write_text(updated, encoding="utf-8")
