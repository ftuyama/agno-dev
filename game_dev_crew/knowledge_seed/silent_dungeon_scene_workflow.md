# *Silent Dungeon* — distilled scene rules (seed KB)

When the game repo is mounted at **`REPO_ROOT`**, prefer the in-repo checklist (if present): **`.cursor/skills/create-scenes/SKILL.md`**.

## Layout

- Scene markdown + YAML frontmatter under `src/campaigns/calvario/scenes/`.
- Engine contracts: **`REPO_ROOT/src/engine/schema/`** (validators and types win over memory).

## Choices & branching

- Map each choice to schema-backed `next` links, conditions, and costs; keep branches explicit so `validate:scenes` can catch orphans.

## npm validation (from `REPO_ROOT`)

- `npm run test` after substantive edits.
- When scenes change, run the project’s scene validator (commonly `npm run validate:scenes`) via allowlisted shell tools only.

## ASCII & highlights

- Terminal-style **ASCII** blocks and choice **highlight** / focus behavior are owned by the UI layer under **`src/ui/`** (components + `src/ui/css/`); keep scene files to copy + data, not presentation hacks.

## Factions & classes

- Allegiances, class gates, and progression flags are data-driven from campaign assets plus engine types—confirm the current enum / field names under `src/campaigns/calvario/` and `src/engine/schema/` before writing new conditions.

## Acts, stats, combat

For a condensed view of **act folders**, **starting stats**, **resources/reputation**, and the **combat turn model**, see **`silent_dungeon_world_and_mechanics.md`** in this same seed pack.
