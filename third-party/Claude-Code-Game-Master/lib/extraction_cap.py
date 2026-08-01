#!/usr/bin/env python3
"""Cap extracted entities to the most playable top-N per type.

Imports extract every entity in a book (65 NPCs, etc.) — too many, dilutes the
playable core, costs tokens downstream. This caps each type (npcs/locations/items/
plots) to the top-N by IMPORTANCE, deterministically, after extraction.

Importance is book-agnostic (no hardcoded names):
  score = source mention-frequency (count across chunks)
        + large boost if the entity is referenced by a plot (plot.npcs / plot.locations)
        + boost for party members (is_party_member)
This guarantees the main cast survives — they are exactly the entities the main
plots reference. Plots themselves rank by type weight (main > others > optional),
then by how connected they are.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from entity_aliases import normalize_entity_name

DEFAULT_LIMIT = 30
_PLOT_REF_BOOST = 100_000
_PARTY_BOOST = 50_000
_PLOT_TYPE_WEIGHT = {"main": 3, "side": 2, "world": 2, "personal": 2, "optional": 1}


def load_corpus(chunks_dir) -> str:
    """Concatenate all chunk text (lowercased) for mention counting."""
    d = Path(chunks_dir)
    if not d.is_dir():
        return ""
    parts = []
    for f in sorted(d.glob("chunk_*.txt")):
        try:
            parts.append(f.read_text(encoding="utf-8", errors="ignore").lower())
        except OSError:
            continue
    return "\n".join(parts)


def plot_reference_names(plots: dict) -> set:
    """Normalized set of every name referenced by any plot (npcs + locations)."""
    refs = set()
    for plot in (plots or {}).values():
        if not isinstance(plot, dict):
            continue
        for key in ("npcs", "locations"):
            for ref in plot.get(key, []) or []:
                n = normalize_entity_name(ref)
                if n:
                    refs.add(n)
    return refs


def mention_count(name: str, corpus: str) -> int:
    if not name or not corpus:
        return 0
    return corpus.count(name.lower())


def importance_score(name, entity, type_name, corpus, plot_refs):
    """Higher = more important / more likely to be kept."""
    if type_name == "plots":
        weight = _PLOT_TYPE_WEIGHT.get((entity or {}).get("type", "").lower(), 1)
        connectedness = len((entity or {}).get("npcs", []) or []) + \
            len((entity or {}).get("locations", []) or []) + \
            len((entity or {}).get("objectives", []) or [])
        return weight * 10_000 + connectedness

    score = mention_count(name, corpus)
    if normalize_entity_name(name) in plot_refs:
        score += _PLOT_REF_BOOST
    if isinstance(entity, dict) and entity.get("is_party_member"):
        score += _PARTY_BOOST
    return score


def cap_type(entities: dict, type_name: str, corpus: str, plot_refs: set, limit: int):
    """Return (kept_dict, dropped_names). Stable: ties broken by original order."""
    if not isinstance(entities, dict) or len(entities) <= limit:
        return entities, []
    items = list(entities.items())
    ranked = sorted(
        enumerate(items),
        key=lambda iv: (importance_score(iv[1][0], iv[1][1], type_name, corpus, plot_refs), -iv[0]),
        reverse=True,
    )
    kept_pairs = [items[i] for i, _ in ranked[:limit]]
    dropped = [items[i][0] for i, _ in ranked[limit:]]
    return dict(kept_pairs), dropped


def cap_campaign(campaign_dir, limit: int = DEFAULT_LIMIT) -> dict:
    """Cap npcs/locations/items/plots files in a campaign root in place.

    Returns a report: {type: {"kept": n, "dropped": [names]}}.
    """
    cdir = Path(campaign_dir)
    corpus = load_corpus(cdir / "chunks")
    plots_path = cdir / "plots.json"
    plots = json.loads(plots_path.read_text()) if plots_path.exists() else {}
    plot_refs = plot_reference_names(plots)

    report = {}
    for type_name in ("npcs", "locations", "items", "plots"):
        path = cdir / f"{type_name}.json"
        if not path.exists():
            continue
        entities = json.loads(path.read_text())
        if not isinstance(entities, dict):
            continue
        kept, dropped = cap_type(entities, type_name, corpus, plot_refs, limit)
        if dropped:
            path.write_text(json.dumps(kept, indent=2))
        report[type_name] = {"kept": len(kept), "dropped": dropped}
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cap extracted entities to top-N per type")
    parser.add_argument("campaign_dir")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    report = cap_campaign(args.campaign_dir, args.limit)
    for t, r in report.items():
        n_drop = len(r["dropped"])
        print(f"  {t}: kept {r['kept']}, dropped {n_drop}")
        if n_drop:
            print(f"    dropped: {', '.join(r['dropped'][:10])}{' ...' if n_drop > 10 else ''}")


if __name__ == "__main__":
    main()
