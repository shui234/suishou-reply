"""Non-secret preferences; API keys never belong in this file."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile


STYLES = ('自然', '犀利', '幽默')
THEMES = ('dark', 'light')


def valid_model(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._:/-]{1,100}', value) is not None


@dataclass
class Settings:
    model: str = 'deepseek-flash'
    style: str = '自然'
    theme: str = 'dark'


def _validated(values: dict) -> Settings:
    defaults = Settings()
    return Settings(
        model=values.get('model') if valid_model(values.get('model')) else defaults.model,
        style=values.get('style') if values.get('style') in STYLES else defaults.style,
        theme=values.get('theme') if values.get('theme') in THEMES else defaults.theme,
    )


class SettingsStore:
    def __init__(self, path: Path | None = None):
        local = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
        self.path = Path(path) if path is not None else local / 'SuishouReply' / 'settings.json'

    def load(self) -> Settings:
        try:
            if self.path.stat().st_size > 65536:
                return Settings()
            values = json.loads(self.path.read_text(encoding='utf-8-sig'))
            return _validated(values) if isinstance(values, dict) else Settings()
        except (OSError, ValueError, UnicodeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        clean = _validated({'model': settings.model, 'style': settings.style, 'theme': settings.theme})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.settings-', suffix='.tmp', delete=False) as handle:
                temporary = handle.name
                json.dump({'model': clean.model, 'style': clean.style, 'theme': clean.theme},
                          handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
