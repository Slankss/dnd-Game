"""Tests for cap-extraction-30: importance-ranked cap of extracted entities."""

import json

from lib.extraction_cap import (
    cap_type,
    cap_campaign,
    importance_score,
    plot_reference_names,
)


def test_plot_referenced_entity_survives_over_high_mention_noise():
    # "Walkon" is mentioned a lot but referenced by no plot; "Hero" is plot-referenced.
    entities = {f"Filler{i}": {} for i in range(40)}
    entities["Hero"] = {}        # plot-referenced, low raw mentions
    entities["Walkon"] = {}      # high mentions, no plot ref
    corpus = ("walkon " * 500) + ("filler0 " * 10) + "hero"
    plot_refs = {"hero"}
    kept, dropped = cap_type(entities, "npcs", corpus, plot_refs, limit=30)
    assert len(kept) == 30
    assert "Hero" in kept, "plot-referenced entity must never be dropped"
    assert "Hero" not in dropped


def test_party_member_survives():
    entities = {f"X{i}": {} for i in range(35)}
    entities["Sidekick"] = {"is_party_member": True}
    kept, dropped = cap_type(entities, "npcs", "", set(), limit=30)
    assert "Sidekick" in kept


def test_no_cap_when_under_limit():
    entities = {f"X{i}": {} for i in range(10)}
    kept, dropped = cap_type(entities, "npcs", "", set(), limit=30)
    assert kept == entities
    assert dropped == []


def test_plots_rank_main_over_optional():
    plots = {f"side{i}": {"type": "side"} for i in range(40)}
    plots["MainArc"] = {"type": "main"}
    plots["Optional1"] = {"type": "optional"}
    kept, dropped = cap_type(plots, "plots", "", set(), limit=30)
    assert "MainArc" in kept
    assert "Optional1" in dropped  # weakest type, displaced by 30 'side' plots


def test_exactly_limit_kept():
    entities = {f"X{i}": {} for i in range(100)}
    kept, _ = cap_type(entities, "items", "corpus", set(), limit=30)
    assert len(kept) == 30


def test_plot_reference_names_normalizes():
    plots = {"P": {"npcs": ["Princess Donut"], "locations": ["Station 81 (hub)"]}}
    refs = plot_reference_names(plots)
    assert "donut" in refs          # title stripped
    assert "station 81" in refs     # parenthetical stripped


def test_cap_campaign_writes_capped_files(tmp_path):
    cdir = tmp_path / "camp"
    (cdir / "chunks").mkdir(parents=True)
    (cdir / "chunks" / "chunk_000.txt").write_text("carl donut " * 20)
    npcs = {f"N{i}": {} for i in range(50)}
    npcs["Carl"] = {}
    (cdir / "npcs.json").write_text(json.dumps(npcs))
    (cdir / "plots.json").write_text(json.dumps({"P": {"type": "main", "npcs": ["Carl"]}}))
    report = cap_campaign(str(cdir), limit=30)
    saved = json.loads((cdir / "npcs.json").read_text())
    assert len(saved) == 30
    assert "Carl" in saved                       # plot-referenced -> survives
    assert report["npcs"]["kept"] == 30
    assert len(report["npcs"]["dropped"]) == 21
