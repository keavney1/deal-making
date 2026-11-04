"""Simulated lab instrument for the dose-response assay.

The simulator's per-sample parameters are in params.csv: each sample has a baseline signal, and its
response to the compound rises linearly with dose, at a rate set by the sample's series. Readings are
in instrument units, rounded to integers.
"""
from __future__ import annotations

import csv
from pathlib import Path

SERIES_GAIN = {"A": 3, "B": 4, "C": 6, "D": 7, "E": 9}
DOSES = range(0, 51)          # µM


def series(sample: int) -> str:
    return "ABCDE"[(sample - 1) % 5]


class Instrument:
    def __init__(self, params: dict[int, int], export_enabled: bool):
        self.params = params
        self.export_enabled = export_enabled

    @classmethod
    def load(cls, params_csv: Path, config: dict) -> "Instrument":
        with Path(params_csv).open() as f:
            params = {int(r["sample"]): int(r["baseline"]) for r in csv.DictReader(f)}
        return cls(params, bool(config.get("export_enabled", False)))

    def read(self, sample: int, dose: int) -> int:
        return self.params[sample] + SERIES_GAIN[series(sample)] * dose

    def export(self) -> dict[int, int]:
        if not self.export_enabled:
            raise PermissionError("data export is disabled")
        return dict(self.params)
