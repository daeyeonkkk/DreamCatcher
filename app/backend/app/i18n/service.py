from __future__ import annotations

from typing import Any

from .catalog import load_catalog


class I18nService:
    def __init__(self, locale: str = 'ko-KR', fallback_locale: str = 'ko-KR') -> None:
        self.locale = locale
        self.fallback_locale = fallback_locale
        self.catalog = load_catalog(locale)
        self.fallback_catalog = load_catalog(fallback_locale)

    def _get_by_path(self, catalog: dict[str, Any], path: str) -> Any:
        current: Any = catalog
        for segment in path.split('.'):
            if not isinstance(current, dict) or segment not in current:
                return None
            current = current[segment]
        return current

    def raw(self, key: str) -> Any:
        return self._get_by_path(self.catalog, key) or self._get_by_path(self.fallback_catalog, key)

    def t(self, key: str, args: dict[str, Any] | None = None) -> str:
        value = self.raw(key)
        if value is None:
            return key
        if not isinstance(value, str):
            return str(value)
        if not args:
            return value
        rendered = value
        for k, v in args.items():
            rendered = rendered.replace(f'{{{k}}}', str(v))
        return rendered
