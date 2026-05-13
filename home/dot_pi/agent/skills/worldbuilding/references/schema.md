# Entry Schema

All entries share a common frontmatter core, plus type-specific fields. Frontmatter is written in a stable key order for clean git diffs:

```
id, type, name, aliases, tags, related, summary, <type-specific fields>, updated
```

## Common fields

| Field      | Required | Notes |
|------------|----------|-------|
| `id`       | yes      | Stable, lowercase-kebab, prefixed by type (`char-`, `loc-`, `fac-`, `item-`, `evt-`, `lore-`, `sess-`). Never renamed. |
| `type`     | yes      | One of: `character`, `location`, `faction`, `item`, `event`, `lore`, `session`. |
| `name`     | yes      | Display name. |
| `aliases`  | no       | Alternate names / epithets (list of strings). |
| `tags`     | no       | Free-form labels (list of strings), lowercase-kebab. |
| `related`  | no       | List of IDs this entry references. Index builds the reverse graph. |
| `summary`  | yes      | 1–2 sentences. Used by the index for cheap bulk loading. |
| `updated`  | yes      | ISO date (YYYY-MM-DD), set automatically on write. |

## Type-specific fields

### `character`
- `role`: e.g. `protagonist`, `antagonist`, `supporting`, `minor`
- `status`: `alive`, `dead`, `missing`, `unknown`
- `affiliations`: list of faction IDs (also include in `related`)
- `location`: current location ID (also include in `related`)

### `location`
- `region`: larger containing area (free text or ID)
- `parent`: parent location ID, if nested

### `faction`
- `allegiance`: `ally`, `enemy`, `neutral`, `unknown`
- `leader`: character ID

### `item`
- `owner`: character ID
- `location`: location ID

### `event`
- `chapter`: integer (story-chapter anchor) — enables `timeline --until-chapter`
- `date`: in-world date, free text or ISO — sorted lexicographically if ISO
- `participants`: list of character IDs
- `where`: location ID

### `lore`
- `category`: `magic`, `religion`, `cosmology`, `history`, `deity`, `prophecy`, ...
  - Deities live here (e.g. `category: deity`) unless they act as on-stage characters, in which case use `character`.

### `session`
- `chapter`: integer
- `pov`: character ID of viewpoint character

### `species`
Races, sapient peoples as a group, and creatures/beasts.
- `habitat`: location ID or free-text region
- `sapient`: `yes`, `no`, `unknown`
- `languages`: list of language names (free text) commonly spoken by this species

### `culture`
Ethnic/regional peoples, distinct from `faction` (political/organizational).
- `region`: location ID or free-text region
- `languages`: list of language names (free text) spoken by the culture
- Use `related` to link associated factions, locations, and species.

### `document`
In-world written artifacts: letters, books, prophecies, inscriptions, edicts.
- `category`: `letter`, `book`, `prophecy`, `inscription`, `edict`, `journal`, ...
- `author`: character ID (or free text if unknown)
- `date`: in-world date or era (free text or ISO)
- Body of the entry is the document's text or an excerpt.

## ID prefixes

| Type       | Prefix   |
|------------|----------|
| character  | `char-`  |
| location   | `loc-`   |
| faction    | `fac-`   |
| item       | `item-`  |
| event      | `evt-`   |
| lore       | `lore-`  |
| session    | `sess-`  |
| species    | `spec-`  |
| culture    | `cult-`  |
| document   | `doc-`   |
