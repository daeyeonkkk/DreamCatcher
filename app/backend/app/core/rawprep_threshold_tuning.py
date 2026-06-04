from __future__ import annotations

from pathlib import Path

from .rawprep_catalog import legacy_removed_note
from .studio_paths import resolve_output_root


def rawprep_threshold_dataset_path(output_root: str = "outputs") -> Path:
    return resolve_output_root(output_root) / "_v2" / "raw_engine_threshold_dataset.json"


def tune_threshold_dataset(*_args, **_kwargs) -> dict[str, object]:
    return {
        "enabled": False,
        "status": "disabled",
        "message": legacy_removed_note(),
    }
