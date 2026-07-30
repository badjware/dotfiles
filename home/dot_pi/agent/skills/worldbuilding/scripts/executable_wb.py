#!/usr/bin/env python3
"""Worldbuilding canon store. Stdlib only.

A flat collection of Markdown entries with minimal YAML frontmatter, used to
ground prose generation. The whole world lives under `./world/` (override
with --world). Files can sit in any subfolder; the index globs `world/**/*.md`.

Frontmatter is a strict subset of YAML:
  - one `key: value` per line
  - values: plain strings, "quoted strings", integers, null/~, flow lists
  - no booleans, no maps, no block style
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Conventions (defaults only, not enforced)
# ---------------------------------------------------------------------------

# Type -> (folder, id-prefix). Used by `new` to pick a sensible default
# location and ID. Unknown types fall back to (`<type>s`, `<type>`).
DEFAULTS = {
    "character": ("characters", "char"),
    "location":  ("locations",  "loc"),
    "faction":   ("factions",   "fac"),
    "item":      ("items",      "item"),
    "event":     ("events",     "evt"),
    "lore":      ("lore",       "lore"),
    "species":   ("species",    "spec"),
    "culture":   ("cultures",   "cult"),
    "document":  ("documents",  "doc"),
}

KEY_ORDER = ["id", "type", "name", "tags", "related", "summary", "chapter", "date"]
REQUIRED = ("id", "type", "name", "summary")

DEFAULT_WORLD_DIR = "world"


def _defaults_for(t: str):
    return DEFAULTS.get(t, (f"{t}s", t))


# ---------------------------------------------------------------------------
# Frontmatter parser / dumper (strict subset)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw == "" or raw.lower() == "null" or raw == "~":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("\"", "'"):
        return raw[1:-1]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def _parse_flow_list(raw: str):
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError(f"expected flow list, got: {raw!r}")
    inner = raw[1:-1].strip()
    if not inner:
        return []
    items, buf, in_str, quote = [], [], False, ""
    for ch in inner:
        if in_str:
            buf.append(ch)
            if ch == quote:
                in_str = False
        elif ch in ("\"", "'"):
            in_str = True; quote = ch; buf.append(ch)
        elif ch == ",":
            items.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return [_parse_scalar(x) for x in items if x.strip()]


def parse_frontmatter(text: str):
    m = _FM_RE.match(text)
    if not m:
        raise ValueError("file has no YAML frontmatter block")
    block, body = m.group(1), m.group(2)
    data = {}
    for lineno, line in enumerate(block.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"line {lineno}: missing ':' in {line!r}")
        key, _, val = line.partition(":")
        key = key.strip(); val = val.strip()
        data[key] = _parse_flow_list(val) if val.startswith("[") else _parse_scalar(val)
    return data, body


def _dump_scalar(v):
    if v is None:
        return ""
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    s = str(v)
    if s == "" or re.search(r"[:\"'#\[\],]", s) or s.strip() != s:
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    return s


def _dump_list(items):
    return "[" + ", ".join(_dump_scalar(x) for x in items) + "]"


def dump_frontmatter(data: dict, body: str) -> str:
    seen, lines = set(), []
    def emit(k, v):
        if isinstance(v, list):
            lines.append(f"{k}: {_dump_list(v)}")
        else:
            lines.append(f"{k}: {_dump_scalar(v)}")
    for k in KEY_ORDER:
        if k in data and data[k] is not None:
            seen.add(k); emit(k, data[k])
    for k in sorted(data):
        if k in seen or data[k] is None:
            continue
        emit(k, data[k])
    body = body.lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.strip().lower())
    return s.strip("-")


def resolve_world_dir(arg: str | None) -> Path:
    p = Path(arg or DEFAULT_WORLD_DIR).expanduser()
    if not p.is_dir():
        raise SystemExit(f"world not found: {p} (create it with `mkdir {p}`)")
    return p


def iter_entry_files(world: Path):
    for f in sorted(world.rglob("*.md")):
        if f.name == "index.json":  # impossible but defensive
            continue
        yield f


def load_entry(path: Path):
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def find_entry_path(world: Path, entry_id: str) -> Path | None:
    for f in iter_entry_files(world):
        if f.stem == entry_id:
            return f
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_new(args):
    world = resolve_world_dir(args.world)
    folder, prefix = _defaults_for(args.type)
    entry_id = args.id or f"{prefix}-{_slugify(args.name)}"
    target_dir = Path(args.dir) if args.dir else world / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{entry_id}.md"
    if path.exists():
        raise SystemExit(f"already exists: {path}")
    data = {
        "id": entry_id,
        "type": args.type,
        "name": args.name,
        "tags": [s.strip() for s in (args.tags or "").split(",") if s.strip()],
        "related": [s.strip() for s in (args.related or "").split(",") if s.strip()],
        "summary": args.summary or "",
    }
    path.write_text(dump_frontmatter(data, f"# {args.name}\n\n"), encoding="utf-8")
    rebuild_index(world)
    print(str(path))


def cmd_get(args):
    world = resolve_world_dir(args.world)
    path = find_entry_path(world, args.id)
    if not path:
        raise SystemExit(f"not found: {args.id}")
    sys.stdout.write(path.read_text(encoding="utf-8"))


def cmd_find(args):
    world = resolve_world_dir(args.world)
    q = (args.q or "").lower()
    out = []
    for f in iter_entry_files(world):
        try:
            d, body = load_entry(f)
        except Exception as e:
            print(f"warn: {f}: {e}", file=sys.stderr); continue
        if args.type and d.get("type") != args.type:
            continue
        if args.tag and args.tag not in (d.get("tags") or []):
            continue
        if args.related and args.related not in (d.get("related") or []):
            continue
        if q:
            hay = " ".join([
                str(d.get("name") or ""),
                str(d.get("summary") or ""),
                " ".join(d.get("tags") or []),
                body,
            ]).lower()
            if q not in hay:
                continue
        out.append({
            "id": d.get("id"), "type": d.get("type"), "name": d.get("name"),
            "summary": d.get("summary"), "tags": d.get("tags") or [],
            "path": str(f.relative_to(world)),
        })
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_related(args):
    world = resolve_world_dir(args.world)
    path = find_entry_path(world, args.id)
    if not path:
        raise SystemExit(f"not found: {args.id}")
    data, _ = load_entry(path)
    outgoing = data.get("related") or []
    incoming = []
    for f in iter_entry_files(world):
        try:
            d, _b = load_entry(f)
        except Exception:
            continue
        if args.id in (d.get("related") or []):
            incoming.append(d.get("id"))

    def resolve(ids):
        result = []
        for i in ids:
            p = find_entry_path(world, i)
            if not p:
                result.append({"id": i, "broken": True})
            else:
                d, _ = load_entry(p)
                result.append({"id": i, "name": d.get("name"), "type": d.get("type"), "summary": d.get("summary")})
        return result

    print(json.dumps({
        "id": args.id,
        "outgoing": resolve(outgoing),
        "incoming": resolve(sorted(set(incoming))),
    }, indent=2, ensure_ascii=False))


def cmd_timeline(args):
    world = resolve_world_dir(args.world)
    events = []
    for f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception:
            continue
        if d.get("type") != "event":
            continue
        ch = d.get("chapter"); date = d.get("date")
        if args.until_chapter is not None and isinstance(ch, int) and ch > args.until_chapter:
            continue
        if args.until_date and isinstance(date, str) and date > args.until_date:
            continue
        events.append({
            "id": d.get("id"), "name": d.get("name"),
            "chapter": ch, "date": date, "summary": d.get("summary"),
        })
    events.sort(key=lambda e: (e["chapter"] if isinstance(e["chapter"], int) else 10**9, e["date"] or ""))
    print(json.dumps(events, indent=2, ensure_ascii=False))


def cmd_index(args):
    world = resolve_world_dir(args.world)
    rebuild_index(world)
    print(str(world / "index.json"))


def rebuild_index(world: Path):
    entries = []
    reverse: dict[str, list[str]] = {}
    for f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception as e:
            print(f"warn: {f}: {e}", file=sys.stderr); continue
        entries.append({
            "id": d.get("id"), "type": d.get("type"), "name": d.get("name"),
            "tags": d.get("tags") or [], "related": d.get("related") or [],
            "summary": d.get("summary") or "",
            "path": str(f.relative_to(world)),
        })
        for r in d.get("related") or []:
            reverse.setdefault(r, []).append(d.get("id"))
    entries.sort(key=lambda e: (e["type"] or "", e["id"] or ""))
    for k in reverse:
        reverse[k] = sorted(set(reverse[k]))
    idx = {
        "count": len(entries),
        "entries": entries,
        "reverse_links": dict(sorted(reverse.items())),
    }
    (world / "index.json").write_text(
        json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_check(args):
    world = resolve_world_dir(args.world)
    ids = set(); dupes = []; issues = []
    for f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception as e:
            issues.append({"file": str(f.relative_to(world)), "error": str(e)}); continue
        eid = d.get("id")
        if not eid:
            issues.append({"file": str(f.relative_to(world)), "error": "missing id"}); continue
        if eid in ids:
            dupes.append(eid)
        ids.add(eid)
        for req in REQUIRED:
            if not d.get(req):
                issues.append({"id": eid, "error": f"missing required field '{req}'"})
    broken = []
    for f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception:
            continue
        for r in d.get("related") or []:
            if r not in ids:
                broken.append({"from": d.get("id"), "to": r})
    report = {"duplicates": sorted(set(dupes)), "issues": issues, "broken_refs": broken}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if dupes or issues or broken:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="wb.py", description="Worldbuilding canon store")
    sub = p.add_subparsers(dest="cmd", required=True)

    def w(s):
        s.add_argument("--world", default=None, help="world directory (default: ./world)")

    s = sub.add_parser("new", help="create a new entry")
    w(s)
    s.add_argument("--type", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--id")
    s.add_argument("--dir", help="folder for the entry (default: ./world/<type>s/)")
    s.add_argument("--tags")
    s.add_argument("--related")
    s.add_argument("--summary")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("get", help="print an entry"); w(s); s.add_argument("id"); s.set_defaults(func=cmd_get)
    s = sub.add_parser("find", help="query entries"); w(s)
    s.add_argument("--type"); s.add_argument("--tag"); s.add_argument("--related"); s.add_argument("--q")
    s.set_defaults(func=cmd_find)
    s = sub.add_parser("related", help="graph neighbors of an entry"); w(s); s.add_argument("id"); s.set_defaults(func=cmd_related)
    s = sub.add_parser("timeline", help="event timeline"); w(s)
    s.add_argument("--until-chapter", type=int); s.add_argument("--until-date")
    s.set_defaults(func=cmd_timeline)
    s = sub.add_parser("index", help="rebuild index.json"); w(s); s.set_defaults(func=cmd_index)
    s = sub.add_parser("check", help="validate references / duplicates / required fields"); w(s); s.set_defaults(func=cmd_check)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
