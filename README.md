# DND-Game

## 🧟 Active game: "Kızıl Çöküş" (zombi kıyamet, özel senaryo)

Bu proje şu an Celil ve Emir için özel yazılmış bir zombi kıyamet senaryosu
oynatıyor — bkz. [`webapp/README.md`](webapp/README.md) çalıştırma talimatları
için. Kısaca:

```bash
cd webapp && ./run.sh
```

sonra tarayıcıda `http://localhost:5050`. Senaryo/dünya metnini değiştirmek
için [`webapp/scenario.py`](webapp/scenario.py) dosyasını düzenleyin. Bu oyun,
ayrı bir API anahtarı gerektirmeden, mevcut Claude Pro/Max girişinizle
(`claude auth login`) çalışır — Claude Code'u arka planda headless modda
çağırır, bu yüzden oyun turları normal Claude Code kullanım kotanızı paylaşır.

---

## Local Skill Library (D&D 5e vendored resources)

This project was also seeded from 9 public D&D/TTRPG "Game Master" resources for Claude Code.
These are unrelated to the zombie game above and nothing here is wired up as the *active* system — see **Next step** at the bottom.

## Layout

```
.claude/skills/     Ready-to-use Claude Code skills — Claude will auto-discover these.
third-party/        Full vendored copies of the "whole DM system" projects (kept intact
                     because their skills depend on repo-root scripts/agents/data and
                     are not safely portable on their own).
```

## What's in `.claude/skills/` (usable immediately in this project)

| Skill dir | From | What it does |
|---|---|---|
| `ttrpg-dice-roller` | [OptionalRule/ttrpg-dice-claude-skill](https://github.com/OptionalRule/ttrpg-dice-claude-skill) | Cryptographically-secure dice roller, full notation (keep/drop, rerolls, explosions, success counting). Pure Python stdlib, self-contained. MIT. |
| `dnd` | [neuralinitiative/claude-dnd-skill](https://github.com/neuralinitiative/claude-dnd-skill) | Full 5e SRD + supplemental data, character/campaign tracking scripts, an optional TV/phone "display" companion app (audio, TTS, web UI). Self-contained monolith. **AGPL-3.0** (copyleft — see Licensing note below). Its optional physical-dice-hardware bridge and setup docs are alongside in `dnd-extras/` (not a skill itself, just support files). |
| `campaign-organizer`, `campaign-qa`, `publish-site`, `session-play`, `session-prep`, `session-wrapup`, `the-midwife`, `ttrpg-expert`, `vault-ingest`, `shared` | [AntTheLimey/gm-apprentice](https://github.com/AntTheLimey/gm-apprentice) | A full campaign-lifecycle toolkit (an Obsidian-style "vault" of markdown files as the source of truth): session prep/play/wrap-up, campaign QA, NPC/relationship/canon tracking, a system-agnostic `ttrpg-expert` reference (this is the closest local match to the "narrative engine" style skills on mcpmarket.com — see note below), and a "vault-ingest" importer. These skills reference each other and `shared/`, all copied as siblings. Content: CC BY-SA 4.0; code: MIT. |

These will show up automatically next time Claude Code loads this project.

## What's in `third-party/` (full systems, not auto-loaded)

Each of these is a **complete, opinionated D&D assistant** (its own CLAUDE.md persona, its own campaign/character file format, its own scripts). They don't share a data model with each other or with `gm-apprentice`/`dnd` above, so running more than one "live" in the same project will conflict. They're vendored in full so each stays functional and inspectable, but nothing auto-activates.

| Folder | From | Style | License |
|---|---|---|---|
| `Claude-Code-Game-Master` | [Sstobo/Claude-Code-Game-Master](https://github.com/Sstobo/Claude-Code-Game-Master) | Deep campaign-memory system: Python `lib/` + `tools/gm-*.sh` wrappers, its own `.claude/skills/gm-*` (combat, spellcasting, dungeon gen, crafting, social, level-up, conditions), agents, hooks, world-state tracking. Meant to *be* the project root (has `install.sh`). Excluded on copy: the author's own personal play-through save (`_backups/tandy`) and README preview media (images/mp3). | **CC BY-NC-SA 4.0 — non-commercial only.** |
| `claude-dnd-dungeon-master` | [owlot/claude-dnd-dungeon-master](https://github.com/owlot/claude-dnd-dungeon-master) | Session-log-driven system: many small `dm-*` skills (start/end session, combat log, NPC/character log, level-up, loot, voice/audio generation via TTS, scene-image generation), plus `agents/` for combat/character tracking and an SRD lookup. | MIT |
| `claude-dungeon-master` | [PinchOfData/claude-dungeon-master](https://github.com/PinchOfData/claude-dungeon-master) | Older/simpler style — not built on the Skill system at all. Its `CLAUDE.md` *is* the whole DM persona+ruleset, referencing `dm-instructions/*.md` for character sheets, combat, spellcasting, NPCs, loot, campaign generation. To use it, its `CLAUDE.md` would need to become this project's root `CLAUDE.md`. | **No LICENSE file in the repo** (only its bundled SRD data sub-folder is separately licensed) — treat the DM-instructions content as all-rights-reserved by the author until you check with them. |
| `skills-weaver` | [nicmarti/skills-weaver](https://github.com/nicmarti/skills-weaver) | The most different one: a Go application (`cmd/`, `internal/`) exposing D&D tools (dice, characters, monsters, maps, treasure, names, images, a web UI) as CLI commands, with a couple of thin Claude skills (`core_agents/skills/*`, `.claude/skills/decision-council`) that shell out to the compiled binary. Needs `go build` to actually run. Trimmed on copy: dev sample maps (63MB), static web assets (33MB), and source PDFs (7MB) — regenerate/re-clone if you need those. | CC BY-SA 4.0 |

## The two mcpmarket.com links

`gm-craft-narrative-storytelling` and `ttrpg-master-narrative-engine` sit behind mcpmarket.com's bot-check (a Vercel JS challenge that blocks non-browser fetches), so I couldn't retrieve their actual SKILL content to vendor it verbatim. Judging only by their titles, the closest already-present equivalents are `Claude-Code-Game-Master`'s `gm-craft` skill (crafting/rewards) and `gm-apprentice`'s `ttrpg-expert` (scenario-writing, world-evolution, campaign-structure — a system-agnostic narrative engine). If you specifically need the mcpmarket versions, open that URL in a real browser and I can vendor whatever it points to.

## Licensing — read before reusing/publishing

This mixes MIT, CC BY-SA 4.0, **CC BY-NC-SA 4.0 (non-commercial)**, **AGPL-3.0 (copyleft — if you modify and run `dnd`'s code as a network service, you must offer the modified source)**, and one project with **no license at all**. Fine for your own personal table use; check each project's LICENSE before redistributing, selling, or shipping a product built on top of it.

## Next step

Nothing is "live" yet — pick one path:
1. **Use the `.claude/skills/` set as-is** (dice roller + SRD/character tools + gm-apprentice's vault workflow) — just start playing, Claude will pick up matching skills automatically.
2. **Adopt one of the `third-party/` full systems** as this project's active DM — that means copying its `CLAUDE.md` (and its `.claude/` if it has one) up to the project root. Tell me which one and I'll wire it up.
