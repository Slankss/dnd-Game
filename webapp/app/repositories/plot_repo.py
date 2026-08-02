"""Olay örgüsü planı — `data/plot.json`."""

import json
from pathlib import Path

from ..models.plot import DEFAULT_PLOT, Plot

BASE_DIR = Path(__file__).resolve().parents[2]
PLOT_FILE = BASE_DIR / "data" / "plot.json"


class PlotRepository:
    def __init__(self, plot_file=None):
        self.plot_file = Path(plot_file) if plot_file else PLOT_FILE

    def load_raw(self) -> dict:
        """Ham sözlük — eksik alanlar `DEFAULT_PLOT` ile tamamlanır.
        Bozuk/okunamayan dosya oyunu düşürmez, boş plana düşer."""
        if not self.plot_file.exists():
            return json.loads(json.dumps(DEFAULT_PLOT))
        try:
            data = json.loads(self.plot_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(DEFAULT_PLOT))
        if not isinstance(data, dict):
            return json.loads(json.dumps(DEFAULT_PLOT))
        return data

    def load(self) -> Plot:
        return Plot.from_dict(self.load_raw())

    def save(self, plot) -> None:
        """Atomik yazma: yarım kalan bir yazma planı bozmasın."""
        body = plot.to_dict() if isinstance(plot, Plot) else plot
        self.plot_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.plot_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.plot_file)
