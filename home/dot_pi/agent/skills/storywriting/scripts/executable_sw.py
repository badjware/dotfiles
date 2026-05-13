#!/usr/bin/env python3
"""Storywriting project CLI. Stdlib only.

Manages outlines, scenes, and compiled chapters/manuscript for a story.
Reads an attached worldbuilding world directly from disk for context.
Never writes to the world.

`draft` and `revise` produce a JSON prompt package — the agent writes prose.
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
# Frontmatter parser (strict subset, matches worldbuilding/scripts/wb.py)
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
        return "null"
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


# Stable frontmatter key order per type.
STORY_KEYS = ["id", "type", "title", "world", "pov_default", "pov_mode", "tense",
              "logline", "tags", "updated"]
OUTLINE_KEYS = ["id", "type", "scope", "chapter", "summary", "updated"]
SCENE_KEYS = ["id", "type", "chapter", "order", "pov", "where", "characters",
              "status", "summary", "word_count", "pov_mode_override",
              "tense_override", "updated"]

KEY_ORDER = {"story": STORY_KEYS, "outline": OUTLINE_KEYS, "scene": SCENE_KEYS}

LIST_FIELDS_SW = {"tags", "characters"}


def dump_frontmatter(data: dict, body: str) -> str:
    t = data.get("type")
    order = KEY_ORDER.get(t, list(data.keys()))
    seen, lines = set(), []
    for k in order:
        if k in data:
            seen.add(k)
            v = data[k]
            if v is None and k in ("pov_mode_override", "tense_override"):
                lines.append(f"{k}: null")
            elif v is None:
                continue
            elif isinstance(v, list):
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
# World helpers (read-only; storywriting never writes to the world)
# ---------------------------------------------------------------------------

WORLD_TYPE_DIRS = ["characters", "locations", "factions", "items", "events",
                   "lore", "sessions", "species", "cultures", "documents"]


def find_world_entry(world_dir: Path, entry_id: str):
    if not world_dir or not world_dir.is_dir():
        return None
    for d in WORLD_TYPE_DIRS:
        p = world_dir / d / f"{entry_id}.md"
        if p.exists():
            try:
                data, body = parse_frontmatter(p.read_text(encoding="utf-8"))
                return {"data": data, "body": body, "path": str(p)}
            except Exception:
                return None
    return None


def world_summary(world_dir: Path, entry_id: str):
    e = find_world_entry(world_dir, entry_id)
    if not e:
        return None
    d = e["data"]
    return {"id": d.get("id"), "name": d.get("name"), "type": d.get("type"),
            "summary": d.get("summary")}


# ---------------------------------------------------------------------------
# Story helpers
# ---------------------------------------------------------------------------

def _today():
    return _dt.date.today().isoformat()


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def resolve_story_dir(arg: str) -> Path:
    p = Path(arg).expanduser()
    if p.is_dir():
        return p
    cand = Path.cwd() / "stories" / arg
    if cand.is_dir():
        return cand
    raise SystemExit(f"story not found: {arg} (also tried {cand})")


def load_story(story: Path):
    f = story / "story.md"
    if not f.exists():
        raise SystemExit(f"not a story dir (missing story.md): {story}")
    data, body = parse_frontmatter(f.read_text(encoding="utf-8"))
    return data, body


def resolve_world_dir(story: Path):
    data, _ = load_story(story)
    wp = data.get("world")
    if not wp:
        return None
    p = (story / wp).resolve() if not os.path.isabs(wp) else Path(wp)
    return p if p.is_dir() else None


def iter_scene_files(story: Path):
    d = story / "scenes"
    if not d.is_dir():
        return
    for f in sorted(d.glob("sc-*.md")):
        try:
            data, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            yield f, data, body
        except Exception as e:
            print(f"warn: {f}: {e}", file=sys.stderr)


def load_scene(story: Path, scene_id: str):
    p = story / "scenes" / f"{scene_id}.md"
    if not p.exists():
        raise SystemExit(f"scene not found: {scene_id}")
    data, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    return p, data, body


def save_file(path: Path, data: dict, body: str):
    data["updated"] = _today()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_frontmatter(data, body), encoding="utf-8")


def word_count(text: str) -> int:
    # Strip frontmatter if present.
    m = _FM_RE.match(text)
    if m:
        text = m.group(2)
    return len(re.findall(r"\S+", text))


_MENTION_RE = re.compile(r"@([a-z]+-[a-z0-9-]+)")
_SCENE_HEAD_RE = re.compile(r"^#\s+sc-[a-z0-9-]+\s*\n+", re.MULTILINE)


def extract_mentions(text: str):
    return sorted(set(_MENTION_RE.findall(text or "")))


def strip_scene_heading(body: str) -> str:
    """Remove the auto-generated '# sc-chNN-sMM' heading from a scene body."""
    return _SCENE_HEAD_RE.sub("", body, count=1).strip()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    parent = Path(args.path).expanduser() if args.path else Path.cwd() / "stories"
    slug = _slugify(args.name)
    root = parent / slug
    if root.exists():
        raise SystemExit(f"already exists: {root}")
    root.mkdir(parents=True)
    for sub in ("outline", "scenes", "chapters", "notes"):
        (root / sub).mkdir()

    world_path = args.world or ""
    if world_path and not os.path.isabs(world_path):
        # Normalize to relative-from-story-dir if target is resolvable.
        candidate = Path(world_path).expanduser().resolve()
        if candidate.is_dir():
            try:
                world_path = os.path.relpath(candidate, root)
            except ValueError:
                world_path = str(candidate)

    story_data = {
        "id": "story",
        "type": "story",
        "title": args.name,
        "world": world_path or None,
        "pov_default": args.pov or None,
        "pov_mode": "limited-third",
        "tense": args.tense or "past",
        "logline": args.logline or "",
        "tags": [],
    }
    save_file(root / "story.md", story_data,
              f"# {args.name}\n\nPremise, themes, and high-level notes go here.\n")

    (root / "STYLE.md").write_text(
        "# Style Guide\n\n"
        "Keep this short and concrete.\n\n"
        "- **POV mode:** limited-third\n"
        "- **Tense:** past\n"
        "- **Vocabulary:** favor concrete sensory detail; avoid abstract filler.\n"
        "- **Dialogue:** minimal tags; let voice carry attribution.\n"
        "- **Pacing:** one viewpoint per scene; no head-hopping.\n",
        encoding="utf-8",
    )
    (root / "notes" / "continuity.md").write_text("# Continuity notes\n\n", encoding="utf-8")
    (root / "notes" / "todo.md").write_text("# TODO\n\n", encoding="utf-8")
    rebuild_index(root)
    print(str(root))


def cmd_new_outline(args):
    story = resolve_story_dir(args.story)
    if args.scope == "arc":
        path = story / "outline" / "arc.md"
        data = {"id": "out-arc", "type": "outline", "scope": "arc", "summary": ""}
        body = "# Arc outline\n\n- Act I: ...\n- Act II: ...\n- Act III: ...\n"
    elif args.scope == "chapter":
        if args.chapter is None:
            raise SystemExit("--chapter required when --scope chapter")
        ch = f"ch{args.chapter:02d}"
        path = story / "outline" / f"{ch}.md"
        data = {"id": f"out-{ch}", "type": "outline", "scope": "chapter",
                "chapter": args.chapter, "summary": ""}
        body = f"# Chapter {args.chapter} outline\n\n- Beat 1: ...\n- Beat 2: ...\n"
    else:
        raise SystemExit("--scope must be arc or chapter")
    if path.exists():
        raise SystemExit(f"already exists: {path}")
    save_file(path, data, body)
    rebuild_index(story)
    print(str(path))


def cmd_new_scene(args):
    story = resolve_story_dir(args.story)
    scene_id = f"sc-ch{args.chapter:02d}-s{args.order:02d}"
    path = story / "scenes" / f"{scene_id}.md"
    if path.exists():
        raise SystemExit(f"already exists: {path}")
    chars = [s.strip() for s in (args.characters or "").split(",") if s.strip()]
    if args.pov and args.pov not in chars:
        chars.insert(0, args.pov)
    data = {
        "id": scene_id,
        "type": "scene",
        "chapter": args.chapter,
        "order": args.order,
        "pov": args.pov,
        "where": args.where,
        "characters": chars,
        "status": "outline",
        "summary": args.summary or "",
        "word_count": 0,
        "pov_mode_override": None,
        "tense_override": None,
    }
    save_file(path, data, f"# {scene_id}\n\n")
    rebuild_index(story)
    print(str(path))


def cmd_set_status(args):
    story = resolve_story_dir(args.story)
    if args.status not in ("outline", "draft", "revised", "final"):
        raise SystemExit(f"invalid status: {args.status}")
    p, data, body = load_scene(story, args.scene_id)
    data["status"] = args.status
    save_file(p, data, body)
    rebuild_index(story)
    print(f"{args.scene_id}: {args.status}")


def _effective_pov_tense(story_data: dict, scene_data: dict):
    pov_mode = scene_data.get("pov_mode_override") or story_data.get("pov_mode") or "limited-third"
    tense = scene_data.get("tense_override") or story_data.get("tense") or "past"
    return pov_mode, tense


def _adjacent_scenes(story: Path, scene_data: dict):
    ch, order = scene_data.get("chapter"), scene_data.get("order")
    prev_f = next_f = None
    best_prev = (-1, -1)
    best_next = (10**9, 10**9)
    for f, d, _b in iter_scene_files(story):
        c, o = d.get("chapter"), d.get("order")
        if c is None or o is None:
            continue
        key = (c, o)
        if key < (ch, order) and key > best_prev:
            best_prev = key; prev_f = (f, d, _b)
        if key > (ch, order) and key < best_next:
            best_next = key; next_f = (f, d, _b)

    def slice_paragraph(body: str, which: str):
        body = strip_scene_heading(body)
        if not body:
            return ""
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        if not paras:
            return ""
        return (paras[-1] if which == "last" else paras[0])[:1000]

    def short(entry, which):
        if not entry:
            return None
        f, d, b = entry
        out = {"id": d.get("id"), "summary": d.get("summary")}
        if which == "last":
            out["last_paragraph"] = slice_paragraph(b, "last")
        else:
            out["first_paragraph"] = slice_paragraph(b, "first")
        return out

    return {"previous": short(prev_f, "last"), "next": short(next_f, "first")}


def _read_optional(p: Path):
    return p.read_text(encoding="utf-8") if p.exists() else None


def _build_package(mode: str, story: Path, scene_id: str, goal: str | None):
    story_data, _ = load_story(story)
    scene_path, scene_data, scene_body = load_scene(story, scene_id)
    pov_mode, tense = _effective_pov_tense(story_data, scene_data)
    world_dir = resolve_world_dir(story)

    warnings = []
    if world_dir is None:
        warnings.append("no attached world directory (story.md 'world' missing or unresolvable)")

    chapter_outline_path = story / "outline" / f"ch{scene_data['chapter']:02d}.md"
    arc_outline_path = story / "outline" / "arc.md"
    arc_outline = None
    if arc_outline_path.exists():
        _, arc_outline = parse_frontmatter(arc_outline_path.read_text(encoding="utf-8"))
    chapter_outline = None
    if chapter_outline_path.exists():
        _, chapter_outline = parse_frontmatter(chapter_outline_path.read_text(encoding="utf-8"))
    else:
        warnings.append(f"no chapter outline for chapter {scene_data['chapter']}")

    style_path = story / "STYLE.md"
    style_guide = style_path.read_text(encoding="utf-8") if style_path.exists() else ""

    # World context.
    def full_entry(eid):
        e = find_world_entry(world_dir, eid) if world_dir else None
        if not e:
            warnings.append(f"unresolved @id: {eid}")
            return None
        return {"frontmatter": e["data"], "body": e["body"].strip()}

    pov_entry = full_entry(scene_data["pov"]) if scene_data.get("pov") else None
    where_entry = full_entry(scene_data["where"]) if scene_data.get("where") else None

    # Mentioned @ids in outlines, summary, goal, and (for revise) existing prose.
    mentioned_ids = set()
    sources = [chapter_outline or "", arc_outline or "",
               scene_data.get("summary") or ""]
    if mode == "revise":
        sources.append(goal or "")
        sources.append(strip_scene_heading(scene_body))
    for src in sources:
        mentioned_ids.update(extract_mentions(src))

    # Don't duplicate pov/where/characters.
    scene_chars = set(scene_data.get("characters") or [])
    exclude = {scene_data.get("pov"), scene_data.get("where")} | scene_chars

    # Goal-focused IDs get FULL entries (critical for dialogue polishing etc.).
    goal_focus_ids = set(extract_mentions(goal or "")) if mode == "revise" else set()
    goal_focus = []
    for gid in sorted(goal_focus_ids - {scene_data.get("pov"), scene_data.get("where")}):
        e = find_world_entry(world_dir, gid) if world_dir else None
        if e is None:
            warnings.append(f"unresolved @id in goal: {gid}")
        else:
            goal_focus.append({"frontmatter": e["data"], "body": e["body"].strip()})

    # Characters listed on the scene also get FULL entries (not just summaries) —
    # body-level voice notes matter for dialogue work.
    char_full = []
    for cid in scene_data.get("characters") or []:
        if cid == scene_data.get("pov"):
            continue
        e = find_world_entry(world_dir, cid) if world_dir else None
        if e is None:
            warnings.append(f"unresolved @id: {cid}")
        else:
            char_full.append({"frontmatter": e["data"], "body": e["body"].strip()})

    mentioned = []
    for mid in sorted(mentioned_ids - exclude - goal_focus_ids):
        s = world_summary(world_dir, mid) if world_dir else None
        if s is None:
            warnings.append(f"unresolved @id: {mid}")
        else:
            mentioned.append(s)

    pkg = {
        "mode": mode,
        "story": {
            "title": story_data.get("title"),
            "logline": story_data.get("logline"),
            "pov_mode": story_data.get("pov_mode"),
            "tense": story_data.get("tense"),
            "pov_default": story_data.get("pov_default"),
        },
        "style_guide": style_guide,
        "arc_outline": arc_outline,
        "chapter_outline": chapter_outline,
        "scene": {
            "id": scene_data.get("id"),
            "chapter": scene_data.get("chapter"),
            "order": scene_data.get("order"),
            "pov": scene_data.get("pov"),
            "pov_mode_effective": pov_mode,
            "tense_effective": tense,
            "where": scene_data.get("where"),
            "characters": scene_data.get("characters") or [],
            "status": scene_data.get("status"),
            "summary": scene_data.get("summary"),
        },
        "adjacent": _adjacent_scenes(story, scene_data),
        "world_context": {
            "pov_character": pov_entry,
            "where": where_entry,
            "characters": char_full,
            "mentioned": mentioned,
            "goal_focus": goal_focus,
        },
        "warnings": warnings,
        "instructions": [
            f"Write in {pov_mode} POV from {scene_data.get('pov')}.",
            f"Use {tense} tense.",
            "Match the tone, vocabulary, and pacing rules in style_guide.",
            "Do not invent canon facts that contradict world_context.",
            "If you name a new entity not in world_context, add a 'TODO:' line at the end of the prose referencing it.",
        ],
    }
    if mode == "revise":
        pkg["existing_prose"] = strip_scene_heading(scene_body)
        pkg["goal"] = goal or ""
        if goal_focus:
            pkg["instructions"].append(
                "Pay special attention to world_context.goal_focus — those entries "
                "are the primary subject of the revision goal."
            )
    return pkg


def cmd_draft(args):
    story = resolve_story_dir(args.story)
    pkg = _build_package("draft", story, args.scene_id, None)
    print(json.dumps(pkg, indent=2, ensure_ascii=False))


def cmd_revise(args):
    story = resolve_story_dir(args.story)
    pkg = _build_package("revise", story, args.scene_id, args.goal)
    print(json.dumps(pkg, indent=2, ensure_ascii=False))


def cmd_continuity(args):
    story = resolve_story_dir(args.story)
    world_dir = resolve_world_dir(story)
    report = {"world": str(world_dir) if world_dir else None,
              "scenes": [], "warnings": []}
    if not world_dir:
        report["warnings"].append("no attached world; cannot validate @id mentions")
    for f, data, body in iter_scene_files(story):
        if args.chapter is not None and data.get("chapter") != args.chapter:
            continue
        mentions = extract_mentions(body) + extract_mentions(data.get("summary") or "")
        ids = []
        for cid in (data.get("pov"), data.get("where")):
            if cid:
                ids.append(cid)
        ids += data.get("characters") or []
        ids += mentions
        broken, unknown = [], []
        for i in sorted(set(ids)):
            if not world_dir:
                continue
            if not find_world_entry(world_dir, i):
                broken.append(i)
        report["scenes"].append({
            "id": data.get("id"),
            "chapter": data.get("chapter"),
            "order": data.get("order"),
            "status": data.get("status"),
            "broken_refs": broken,
        })
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if any(s["broken_refs"] for s in report["scenes"]):
        sys.exit(1)


def cmd_compile(args):
    story = resolve_story_dir(args.story)
    # Group scenes by chapter.
    by_chapter: dict[int, list] = {}
    for f, data, body in iter_scene_files(story):
        by_chapter.setdefault(data["chapter"], []).append((data, body))
    for ch, items in by_chapter.items():
        items.sort(key=lambda x: x[0].get("order") or 0)

    chapters_to_build = [args.chapter] if args.chapter is not None else sorted(by_chapter.keys())
    SCENE_BREAK = "* * *"
    for ch in chapters_to_build:
        if ch not in by_chapter:
            continue
        parts = [f"# Chapter {ch}\n"]
        clean_scenes = [strip_scene_heading(b) for _, b in by_chapter[ch]]
        clean_scenes = [s for s in clean_scenes if s]
        for i, clean in enumerate(clean_scenes):
            if i > 0:
                parts.append(SCENE_BREAK + "\n")
            parts.append(clean + "\n")
        out = story / "chapters" / f"ch{ch:02d}.md"
        out.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    # Full manuscript (only when no specific chapter requested, or always refresh).
    if args.chapter is None:
        story_data, _ = load_story(story)
        parts = [f"# {story_data.get('title') or ''}\n"]
        for ch in sorted(by_chapter.keys()):
            ch_file = story / "chapters" / f"ch{ch:02d}.md"
            if ch_file.exists():
                parts.append(ch_file.read_text(encoding="utf-8").strip() + "\n")
        (story / "manuscript.md").write_text("\n".join(parts).rstrip() + "\n",
                                             encoding="utf-8")
    rebuild_index(story)
    print("compiled")


def cmd_status(args):
    story = resolve_story_dir(args.story)
    story_data, _ = load_story(story)
    scenes = []
    totals = {"outline": 0, "draft": 0, "revised": 0, "final": 0, "words": 0}
    for f, data, body in iter_scene_files(story):
        wc = word_count(body)
        totals[data.get("status") or "outline"] = totals.get(data.get("status") or "outline", 0) + 1
        totals["words"] += wc
        scenes.append({
            "id": data.get("id"),
            "chapter": data.get("chapter"),
            "order": data.get("order"),
            "status": data.get("status"),
            "word_count": wc,
            "summary": data.get("summary"),
        })
    scenes.sort(key=lambda s: (s["chapter"] or 0, s["order"] or 0))
    todo_path = story / "notes" / "todo.md"
    todos = todo_path.read_text(encoding="utf-8") if todo_path.exists() else ""
    print(json.dumps({
        "title": story_data.get("title"),
        "totals": totals,
        "scenes": scenes,
        "todo": todos,
    }, indent=2, ensure_ascii=False))


def cmd_index(args):
    story = resolve_story_dir(args.story)
    rebuild_index(story)
    print(str(story / "index.json"))


def rebuild_index(story: Path):
    scenes = []
    for f, data, body in iter_scene_files(story):
        wc = word_count(body)
        # Keep scene's recorded word_count in sync.
        if data.get("word_count") != wc:
            data["word_count"] = wc
            save_file(f, data, body)
        scenes.append({
            "id": data.get("id"),
            "chapter": data.get("chapter"),
            "order": data.get("order"),
            "pov": data.get("pov"),
            "where": data.get("where"),
            "characters": data.get("characters") or [],
            "status": data.get("status"),
            "summary": data.get("summary"),
            "word_count": wc,
            "path": str(f.relative_to(story)),
        })
    scenes.sort(key=lambda s: (s["chapter"] or 0, s["order"] or 0))
    outlines = []
    for f in sorted((story / "outline").glob("*.md")) if (story / "outline").is_dir() else []:
        try:
            d, _b = parse_frontmatter(f.read_text(encoding="utf-8"))
            outlines.append({"id": d.get("id"), "scope": d.get("scope"),
                             "chapter": d.get("chapter"),
                             "path": str(f.relative_to(story))})
        except Exception:
            continue
    idx = {
        "generated": _today(),
        "scene_count": len(scenes),
        "total_words": sum(s["word_count"] for s in scenes),
        "scenes": scenes,
        "outlines": outlines,
    }
    (story / "index.json").write_text(
        json.dumps(idx, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def cmd_expand(args):
    story = resolve_story_dir(args.story)
    world_dir = resolve_world_dir(story)
    text = args.text if args.text is not None else sys.stdin.read()

    def repl(m):
        i = m.group(1)
        e = find_world_entry(world_dir, i) if world_dir else None
        if not e:
            return f"@{i}(?)"
        return f"{e['data'].get('name')} (@{i})"

    sys.stdout.write(_MENTION_RE.sub(repl, text))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="sw.py", description="Storywriting project CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a new story")
    s.add_argument("name")
    s.add_argument("--path", help="parent directory (default: ./stories)")
    s.add_argument("--world", help="path to a worldbuilding world folder")
    s.add_argument("--pov", help="default POV character ID (e.g. char-elira-vance)")
    s.add_argument("--tense", choices=["past", "present"])
    s.add_argument("--logline")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("new-outline", help="create an outline file")
    s.add_argument("story")
    s.add_argument("--scope", required=True, choices=["arc", "chapter"])
    s.add_argument("--chapter", type=int)
    s.set_defaults(func=cmd_new_outline)

    s = sub.add_parser("new-scene", help="create a new scene")
    s.add_argument("story")
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--order", type=int, required=True)
    s.add_argument("--pov", required=True)
    s.add_argument("--where")
    s.add_argument("--characters")
    s.add_argument("--summary")
    s.set_defaults(func=cmd_new_scene)

    s = sub.add_parser("set-status", help="set a scene's status")
    s.add_argument("story"); s.add_argument("scene_id"); s.add_argument("status")
    s.set_defaults(func=cmd_set_status)

    s = sub.add_parser("draft", help="produce a JSON prompt package to draft a scene")
    s.add_argument("story"); s.add_argument("scene_id")
    s.set_defaults(func=cmd_draft)

    s = sub.add_parser("revise", help="produce a JSON prompt package to revise a scene")
    s.add_argument("story"); s.add_argument("scene_id")
    s.add_argument("--goal", required=True)
    s.set_defaults(func=cmd_revise)

    s = sub.add_parser("continuity", help="scan scenes for broken @id references")
    s.add_argument("story"); s.add_argument("--chapter", type=int)
    s.set_defaults(func=cmd_continuity)

    s = sub.add_parser("compile", help="compile scenes → chapters → manuscript")
    s.add_argument("story"); s.add_argument("--chapter", type=int)
    s.set_defaults(func=cmd_compile)

    s = sub.add_parser("status", help="status report (JSON)")
    s.add_argument("story")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("index", help="rebuild index.json")
    s.add_argument("story")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("expand", help="expand @id mentions via attached world")
    s.add_argument("story"); s.add_argument("--text")
    s.set_defaults(func=cmd_expand)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
