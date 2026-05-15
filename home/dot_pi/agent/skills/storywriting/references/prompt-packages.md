# Prompt Packages

`sw.py draft` and `sw.py revise` produce a deterministic JSON "prompt package" that the agent then uses to write prose. The skill itself does not call an LLM.

The package is designed so the agent has everything it needs — POV, tense, style, outline context, adjacent scenes, and world canon — without reading any additional files.

## Shape

```json
{
  "mode": "draft",
  "story": {
    "title": "Cold Case",
    "logline": "...",
    "pov_mode": "limited-third",
    "tense": "past",
    "pov_default": "char-jane-doe"
  },
  "style_guide": "<contents of STYLE.md, verbatim>",
  "arc_outline": "<contents of outline/arc.md body>",
  "chapter_outline": "<contents of outline/ch-01.md body, or null>",
  "scene": {
    "id": "sc-ch01-s03",
    "chapter": 1,
    "order": 3,
    "pov": "char-jane-doe",
    "pov_mode_effective": "limited-third",
    "tense_effective": "past",
    "where": "loc-precinct-12",
    "characters": ["char-jane-doe", "char-mark-lin"],
    "status": "outline",
    "summary": "Jane reopens the file at Precinct 12."
  },
  "adjacent": {
    "previous": {"id": "sc-ch01-s02", "summary": "...", "last_paragraph": "..."},
    "next":     {"id": "sc-ch01-s04", "summary": "...", "first_paragraph": "..."}
  },
  "world_context": {
    "pov_character": { "frontmatter": {...}, "body": "..." },
    "where":         { "frontmatter": {...}, "body": "..." },
    "characters":    [ { "frontmatter": {...}, "body": "..." } ],
    "mentioned":     [ { "id": "...", "name": "...", "summary": "..." } ],
    "goal_focus":    [ { "frontmatter": {...}, "body": "..." } ]
  },
  "existing_prose": "<only present for revise mode>",
  "goal": "<only present for revise mode; free-text instruction>",
  "warnings": [
    "no chapter outline for chapter 1",
    "unresolved @id reference: @loc-unknown in scene summary"
  ],
  "instructions": [
    "Write in limited-third POV from char-jane-doe.",
    "Use past tense.",
    "Match the tone and vocabulary rules in style_guide.",
    "Do not invent canon facts that contradict world_context.",
    "If you name a new entity, add a TODO: line referencing it."
  ]
}
```

## Field sources

| Package field          | Source                                               |
|------------------------|------------------------------------------------------|
| `story`                | `story.md` frontmatter                               |
| `style_guide`          | `STYLE.md` (body only)                               |
| `arc_outline`          | `outline/arc.md` body (or null)                      |
| `chapter_outline`      | `outline/ch-NN.md` body where NN = scene chapter     |
| `scene`                | scene file frontmatter; `*_effective` applies any override |
| `adjacent.previous`    | scene with `chapter==N, order==K-1` (or last of chapter N-1); includes `last_paragraph` |
| `adjacent.next`        | scene with `chapter==N, order==K+1` (or first of chapter N+1); includes `first_paragraph` |
| `world_context.pov_character` / `where` | full world entry (frontmatter + body) |
| `world_context.characters` | full entries for every character listed on the scene (body-level notes like voice/mannerisms stay intact) |
| `world_context.mentioned` | summaries for `@id`s found in outlines, scene summary, goal, and (revise) existing prose |
| `world_context.goal_focus` | **revise only** — full entries for any `@id` mentioned in `--goal`. Primary subjects of the revision. |
| `warnings`             | computed: missing outline, broken `@id`, missing world, etc. |

## Agent usage

1. Call `sw.py draft <story> <scene-id>` (or `revise ... --goal ...`).
2. Read every field in the returned JSON. Do **not** consult memory or other files for facts.
3. Surface any `warnings` to the user before writing prose they would affect.
4. Write prose that obeys `instructions`, the effective POV/tense, and the style guide.
5. Save the prose into the body of the scene file, preserving its frontmatter.
6. Run `sw.py index <story>` to refresh `word_count` and the index.
7. Run `sw.py continuity <story> --chapter N` and report any new broken references.

## Revise mode specifics

`revise` packages include:
- `existing_prose`: the current scene body, with the placeholder `# sc-...` heading stripped.
- `goal`: the user-supplied revision objective.
- `world_context.goal_focus`: full entries for any `@id` mentioned in the goal (e.g. a character whose dialogue you are polishing). The agent should prioritize the body-level notes in these entries (voice, mannerisms, speech patterns).

The agent should return a full rewritten body (not a diff), preserving frontmatter. Do **not** re-introduce the `# sc-...` placeholder heading — the compile step expects it absent.
