#!/usr/bin/env python3
"""Worldbuilding knowledge-base CLI. Stdlib only.

Entries are Markdown files with YAML-ish frontmatter. A minimal, strict
frontmatter parser handles only the schema documented in references/schema.md:
  - string scalars (plain or "quoted")
  - integer scalars
  - flow-style lists: [a, b, "c"]
It does NOT attempt to be a general YAML parser.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Type registry
# ---------------------------------------------------------------------------

TYPES = {
    "character": {"dir": "characters", "prefix": "char-"},
    "location":  {"dir": "locations",  "prefix": "loc-"},
    "faction":   {"dir": "factions",   "prefix": "fac-"},
    "item":      {"dir": "items",      "prefix": "item-"},
    "event":     {"dir": "events",     "prefix": "evt-"},
    "lore":      {"dir": "lore",       "prefix": "lore-"},
    "session":   {"dir": "sessions",   "prefix": "sess-"},
    "species":   {"dir": "species",    "prefix": "spec-"},
    "culture":   {"dir": "cultures",   "prefix": "cult-"},
    "document":  {"dir": "documents",  "prefix": "doc-"},
}

PREFIX_TO_TYPE = {v["prefix"]: t for t, v in TYPES.items()}

COMMON_KEY_ORDER = ["id", "type", "name", "aliases", "tags", "related", "summary"]
TYPE_KEYS = {
    "character": ["role", "status", "affiliations", "location"],
    "location":  ["region", "parent"],
    "faction":   ["allegiance", "leader"],
    "item":      ["owner", "location"],
    "event":     ["chapter", "date", "participants", "where"],
    "lore":      ["category"],
    "session":   ["chapter", "pov"],
    "species":   ["habitat", "sapient", "languages"],
    "culture":   ["region", "languages"],
    "document":  ["category", "author", "date"],
}
TAIL_KEYS = ["updated"]

LIST_FIELDS = {"aliases", "tags", "related", "affiliations", "participants", "languages"}
INT_FIELDS = {"chapter"}


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
            in_str = True
            quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return [_parse_scalar(x) for x in items if x.strip() != ""]


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
            raise ValueError(f"frontmatter line {lineno}: missing ':': {line!r}")
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("["):
            data[key] = _parse_flow_list(val)
        else:
            data[key] = _parse_scalar(val)
    return data, body


def _dump_scalar(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if s == "" or re.search(r"[:\"'#\[\],]", s) or s.strip() != s:
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    return s


def _dump_list(items):
    return "[" + ", ".join(_dump_scalar(x) for x in items) + "]"


def dump_frontmatter(data: dict, body: str) -> str:
    t = data.get("type")
    order = list(COMMON_KEY_ORDER)
    if t in TYPE_KEYS:
        order += TYPE_KEYS[t]
    order += TAIL_KEYS
    seen, lines = set(), []
    for k in order:
        if k in data and data[k] is not None:
            seen.add(k)
            v = data[k]
            if isinstance(v, list):
                lines.append(f"{k}: {_dump_list(v)}")
            else:
                lines.append(f"{k}: {_dump_scalar(v)}")
    for k in sorted(data.keys()):
        if k in seen or data[k] is None:
            continue
        v = data[k]
        if isinstance(v, list):
            lines.append(f"{k}: {_dump_list(v)}")
        else:
            lines.append(f"{k}: {_dump_scalar(v)}")
    body = body.lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today():
    return _dt.date.today().isoformat()


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def resolve_world_dir(arg: str) -> Path:
    p = Path(arg).expanduser()
    if p.is_dir():
        return p
    cand = Path.cwd() / "worlds" / arg
    if cand.is_dir():
        return cand
    raise SystemExit(f"world not found: {arg} (also tried {cand})")


def iter_entry_files(world: Path):
    for t, meta in TYPES.items():
        d = world / meta["dir"]
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            yield t, f


def load_entry(path: Path):
    text = path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(text)
    return data, body


def save_entry(path: Path, data: dict, body: str):
    data["updated"] = _today()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_frontmatter(data, body), encoding="utf-8")


def find_entry_path(world: Path, entry_id: str) -> Path | None:
    prefix = entry_id.split("-", 1)[0] + "-"
    t = PREFIX_TO_TYPE.get(prefix)
    if t:
        p = world / TYPES[t]["dir"] / f"{entry_id}.md"
        if p.exists():
            return p
    for _, f in iter_entry_files(world):
        if f.stem == entry_id:
            return f
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    parent = Path(args.path).expanduser() if args.path else Path.cwd() / "worlds"
    slug = _slugify(args.name)
    root = parent / slug
    if root.exists():
        raise SystemExit(f"already exists: {root}")
    root.mkdir(parents=True)
    for meta in TYPES.values():
        (root / meta["dir"]).mkdir()
    (root / "world.md").write_text(dump_frontmatter(
        {
            "id": "world",
            "type": "lore",
            "name": args.name,
            "tags": [],
            "related": [],
            "summary": f"Top-level notes for the world '{args.name}'.",
            "category": "overview",
        },
        f"# {args.name}\n\nPremise, tone, and high-level rules go here.\n",
    ), encoding="utf-8")
    rebuild_index(root)
    print(str(root))


def cmd_new(args):
    world = resolve_world_dir(args.world)
    if args.type not in TYPES:
        raise SystemExit(f"unknown type: {args.type}")
    meta = TYPES[args.type]
    entry_id = args.id or (meta["prefix"] + _slugify(args.name))
    if not entry_id.startswith(meta["prefix"]):
        raise SystemExit(f"id '{entry_id}' must start with '{meta['prefix']}'")
    path = world / meta["dir"] / f"{entry_id}.md"
    if path.exists():
        raise SystemExit(f"already exists: {path}")
    data = {
        "id": entry_id,
        "type": args.type,
        "name": args.name,
        "aliases": [],
        "tags": [s.strip() for s in (args.tags or "").split(",") if s.strip()],
        "related": [s.strip() for s in (args.related or "").split(",") if s.strip()],
        "summary": args.summary or "",
    }
    body = f"# {args.name}\n\n"
    save_entry(path, data, body)
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
    results = []
    for t, f in iter_entry_files(world):
        data, body = load_entry(f)
        if args.type and data.get("type") != args.type:
            continue
        if args.tag and args.tag not in (data.get("tags") or []):
            continue
        if args.related and args.related not in (data.get("related") or []):
            continue
        if q:
            hay = " ".join([
                str(data.get("name") or ""),
                str(data.get("summary") or ""),
                " ".join(data.get("aliases") or []),
                " ".join(data.get("tags") or []),
                body,
            ]).lower()
            if q not in hay:
                continue
        results.append({
            "id": data.get("id"),
            "type": data.get("type"),
            "name": data.get("name"),
            "summary": data.get("summary"),
            "tags": data.get("tags") or [],
            "path": str(f.relative_to(world)),
        })
    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_related(args):
    world = resolve_world_dir(args.world)
    target = args.id
    path = find_entry_path(world, target)
    if not path:
        raise SystemExit(f"not found: {target}")
    data, _ = load_entry(path)
    outgoing = data.get("related") or []
    incoming = []
    for _, f in iter_entry_files(world):
        d, _b = load_entry(f)
        if target in (d.get("related") or []):
            incoming.append(d.get("id"))

    def resolve(ids):
        out = []
        for i in ids:
            p = find_entry_path(world, i)
            if p:
                d, _ = load_entry(p)
                out.append({"id": i, "name": d.get("name"), "type": d.get("type"), "summary": d.get("summary")})
            else:
                out.append({"id": i, "name": None, "type": None, "summary": None, "broken": True})
        return out

    print(json.dumps({
        "id": target,
        "outgoing": resolve(outgoing),
        "incoming": resolve(incoming),
    }, indent=2, ensure_ascii=False))


def cmd_timeline(args):
    world = resolve_world_dir(args.world)
    events = []
    for t, f in iter_entry_files(world):
        if t != "event":
            continue
        d, _ = load_entry(f)
        ch = d.get("chapter")
        date = d.get("date")
        if args.until_chapter is not None and isinstance(ch, int) and ch > args.until_chapter:
            continue
        if args.until_date and isinstance(date, str) and date > args.until_date:
            continue
        events.append({
            "id": d.get("id"), "name": d.get("name"),
            "chapter": ch, "date": date,
            "summary": d.get("summary"),
        })
    events.sort(key=lambda e: (
        e["chapter"] if isinstance(e["chapter"], int) else 10**9,
        e["date"] or "",
    ))
    print(json.dumps(events, indent=2, ensure_ascii=False))


_MENTION_RE = re.compile(r"@([a-z]+-[a-z0-9-]+)")


def cmd_expand(args):
    world = resolve_world_dir(args.world)
    text = args.text if args.text is not None else sys.stdin.read()

    def repl(m):
        i = m.group(1)
        p = find_entry_path(world, i)
        if not p:
            return f"@{i}(?)"
        d, _ = load_entry(p)
        return f"{d.get('name')} (@{i})"

    sys.stdout.write(_MENTION_RE.sub(repl, text))


def cmd_index(args):
    world = resolve_world_dir(args.world)
    rebuild_index(world)
    print(str(world / "index.json"))


def rebuild_index(world: Path):
    entries = []
    reverse: dict[str, list[str]] = {}
    for t, f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception as e:
            print(f"warn: {f}: {e}", file=sys.stderr)
            continue
        entries.append({
            "id": d.get("id"),
            "type": d.get("type"),
            "name": d.get("name"),
            "aliases": d.get("aliases") or [],
            "tags": d.get("tags") or [],
            "related": d.get("related") or [],
            "summary": d.get("summary") or "",
            "path": str(f.relative_to(world)),
            "updated": d.get("updated"),
        })
        for r in d.get("related") or []:
            reverse.setdefault(r, []).append(d.get("id"))
    entries.sort(key=lambda e: (e["type"] or "", e["id"] or ""))
    for k in reverse:
        reverse[k] = sorted(set(reverse[k]))
    idx = {
        "generated": _today(),
        "count": len(entries),
        "entries": entries,
        "reverse_links": dict(sorted(reverse.items())),
    }
    (world / "index.json").write_text(
        json.dumps(idx, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def cmd_check(args):
    world = resolve_world_dir(args.world)
    ids = set()
    dupes = []
    issues = []
    for t, f in iter_entry_files(world):
        try:
            d, _ = load_entry(f)
        except Exception as e:
            issues.append({"file": str(f.relative_to(world)), "error": str(e)})
            continue
        eid = d.get("id")
        if not eid:
            issues.append({"file": str(f.relative_to(world)), "error": "missing id"})
            continue
        if eid in ids:
            dupes.append(eid)
        ids.add(eid)
        for req in ("type", "name", "summary"):
            if not d.get(req):
                issues.append({"id": eid, "error": f"missing required field '{req}'"})
    broken = []
    for t, f in iter_entry_files(world):
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
    p = argparse.ArgumentParser(prog="wb.py", description="Worldbuilding knowledge-base CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a new world")
    s.add_argument("name")
    s.add_argument("--path", help="parent directory (default: ./worlds)")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("new", help="create a new entry")
    s.add_argument("world")
    s.add_argument("--type", required=True, choices=list(TYPES.keys()))
    s.add_argument("--name", required=True)
    s.add_argument("--id")
    s.add_argument("--tags")
    s.add_argument("--related")
    s.add_argument("--summary")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("get", help="print an entry's file contents")
    s.add_argument("world"); s.add_argument("id")
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("find", help="query entries")
    s.add_argument("world")
    s.add_argument("--type", choices=list(TYPES.keys()))
    s.add_argument("--tag")
    s.add_argument("--related")
    s.add_argument("--q")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("related", help="graph neighbors of an entry")
    s.add_argument("world"); s.add_argument("id")
    s.set_defaults(func=cmd_related)

    s = sub.add_parser("timeline", help="event timeline")
    s.add_argument("world")
    s.add_argument("--until-chapter", type=int)
    s.add_argument("--until-date")
    s.set_defaults(func=cmd_timeline)

    s = sub.add_parser("expand", help="expand @id mentions in text")
    s.add_argument("world")
    s.add_argument("--text")
    s.set_defaults(func=cmd_expand)

    s = sub.add_parser("index", help="rebuild index.json")
    s.add_argument("world")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("check", help="validate references / duplicates / required fields")
    s.add_argument("world")
    s.set_defaults(func=cmd_check)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
