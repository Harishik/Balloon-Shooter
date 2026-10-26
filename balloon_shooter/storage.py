"""Settings and player profile, saved as JSON in the user's data folder."""

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields


def data_dir():
    override = os.environ.get("BALLOON_SHOOTER_HOME")
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "BalloonShooter3D")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/BalloonShooter3D")
    base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "balloon-shooter-3d")


@dataclass
class Settings:
    master_volume: float = 0.8
    music_volume: float = 0.6
    sfx_volume: float = 0.9
    fullscreen: bool = False
    quality: str = "high"          # "high" adds bloom and denser clouds
    screen_shake: bool = True
    show_fps: bool = False
    difficulty: str = "normal"
    last_mode: str = "time"


@dataclass
class Profile:
    best: dict = field(default_factory=dict)        # "mode:difficulty" -> score
    medals: dict = field(default_factory=dict)      # "mode:difficulty" -> best medal index
    total_popped: int = 0
    total_games: int = 0
    best_chain: int = 0

    def best_for(self, mode, difficulty):
        return self.best.get(f"{mode}:{difficulty}", 0)

    def record(self, session):
        """Fold a finished session in. Returns True if it set a new best."""
        key = f"{session.mode.key}:{session.difficulty.key}"
        self.total_games += 1
        self.total_popped += session.popped
        self.best_chain = max(self.best_chain, session.best_chain)
        medal = session.medal()
        if medal > self.medals.get(key, -1):
            self.medals[key] = medal
        if session.score > self.best.get(key, 0):
            self.best[key] = session.score
            return True
        return False


def _load(cls, path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return cls()
    if not isinstance(raw, dict):
        return cls()
    known = {f.name for f in fields(cls)}
    obj = cls()
    for k, v in raw.items():
        if k not in known:
            continue
        current = getattr(obj, k)
        if isinstance(current, float) and isinstance(v, int) and not isinstance(v, bool):
            v = float(v)
        if type(v) is type(current):
            setattr(obj, k, v)
    return obj


def _save(obj, path):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(obj), fh, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass   # never crash the game over a save file


class Store:
    def __init__(self, root=None):
        self.root = root or data_dir()
        self.settings = _load(Settings, self._path("settings.json"))
        self.profile = _load(Profile, self._path("profile.json"))

    def _path(self, name):
        return os.path.join(self.root, name)

    def save(self):
        _save(self.settings, self._path("settings.json"))
        _save(self.profile, self._path("profile.json"))
