from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[3]
LOCALE_DIR = BASE_DIR / 'frontend' / 'src' / 'i18n' / 'locales'


@lru_cache(maxsize=8)
def load_catalog(locale: str) -> dict[str, Any]:
    path = LOCALE_DIR / f'{locale}.json'
    if not path.exists():
        raise FileNotFoundError(f'Locale file not found: {path}')
    return json.loads(path.read_text(encoding='utf-8'))
