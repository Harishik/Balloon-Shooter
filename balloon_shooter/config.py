"""Static game data: balloon catalogue, modes, difficulties and tuning.

Nothing in here imports Panda3D so the rules can be unit-tested headless.
"""

from dataclasses import dataclass, field

TITLE = "Balloon Shooter 3D"

# --- Camera / arena -------------------------------------------------------
FOV_VERTICAL = 58.0          # degrees
NEAR_DEPTH = 15.0            # closest balloon lane (world units in front of camera)
FAR_DEPTH = 38.0             # furthest balloon lane
SPAWN_MARGIN = 3.0           # how far below the view a balloon starts
ESCAPE_MARGIN = 2.5          # how far above the view it counts as escaped

# --- Weapon ---------------------------------------------------------------
FIRE_COOLDOWN = 0.14         # seconds between shots
AUTO_FIRE_COOLDOWN = 0.20    # while the trigger is held
NOVA_RADIUS = 7.0            # area blast radius

# --- Combo ----------------------------------------------------------------
COMBO_WINDOW = 2.2           # seconds to land the next hit
COMBO_STEP = 5               # hits per multiplier level
COMBO_MAX_MULT = 5
STREAK_CALLOUTS = {10: "Nice!", 20: "Great!", 35: "Amazing!", 50: "Unstoppable!", 80: "Legendary!"}

# --- Power-ups ------------------------------------------------------------
SLOWMO_DURATION = 5.0
SLOWMO_SCALE = 0.4
CLOCK_BONUS = 3.0            # seconds added in Time Attack
CLOCK_MAX_TIME = 40.0        # clocks only appear when the timer is below this


@dataclass(frozen=True)
class BalloonKind:
    key: str
    name: str
    color: tuple            # base RGB 0..1
    points: int
    speed: float            # rise-speed multiplier
    size: float             # radius multiplier
    hp: int = 1
    wobble: float = 1.0     # sideways sway multiplier
    glow: float = 0.0       # emissive strength in the shader
    description: str = ""
    modes: tuple = ("time", "survival", "zen")


# Classic balloons come in a cheerful palette; they all score the same.
CLASSIC_COLORS = [
    (0.95, 0.22, 0.28),   # red
    (1.00, 0.55, 0.15),   # orange
    (1.00, 0.82, 0.20),   # yellow
    (0.35, 0.80, 0.35),   # green
    (0.95, 0.40, 0.70),   # pink
    (0.62, 0.40, 0.95),   # purple
    (0.20, 0.75, 0.80),   # teal
]

KINDS = {
    "classic": BalloonKind("classic", "Classic", (0.95, 0.22, 0.28), 10, 1.0, 1.0,
                           description="Pop it! +10"),
    "swift": BalloonKind("swift", "Swift", (0.18, 0.45, 1.0), 25, 1.75, 0.78, wobble=1.6,
                         description="Small and fast. +25"),
    "gold": BalloonKind("gold", "Golden", (1.0, 0.78, 0.25), 100, 1.45, 0.9, wobble=2.4, glow=0.35,
                        description="Rare and zig-zagging. +100"),
    "armored": BalloonKind("armored", "Armored", (0.72, 0.76, 0.82), 60, 0.7, 1.25, hp=3,
                           description="Takes 3 hits. +60"),
    "bomb": BalloonKind("bomb", "Bomb", (0.14, 0.13, 0.16), -50, 0.9, 1.05, glow=0.25,
                        description="Don't hit it! Breaks your combo.",
                        modes=("time", "survival")),
    "frost": BalloonKind("frost", "Frost", (0.55, 0.90, 1.0), 20, 1.1, 0.95, glow=0.3,
                         description="Slows time for a few seconds."),
    "nova": BalloonKind("nova", "Nova", (0.85, 0.30, 1.0), 40, 1.0, 1.0, glow=0.5,
                        description="Blasts every balloon around it."),
    "clock": BalloonKind("clock", "Clock", (0.30, 0.95, 0.55), 15, 1.2, 0.95, glow=0.3,
                         description="+3 seconds on the clock.", modes=("time",)),
    "heart": BalloonKind("heart", "Heart", (1.0, 0.35, 0.50), 15, 1.2, 0.95, glow=0.3,
                         description="Restores one life.", modes=("survival",)),
}

# Base spawn weights. Difficulty and game time adjust these at runtime.
SPAWN_WEIGHTS = {
    "classic": 62.0,
    "swift": 12.0,
    "gold": 2.2,
    "armored": 5.0,
    "bomb": 8.0,
    "frost": 2.5,
    "nova": 2.5,
    "clock": 3.0,
    "heart": 2.0,
}


@dataclass(frozen=True)
class Difficulty:
    key: str
    name: str
    speed: float           # balloon rise speed multiplier
    spawn: float           # spawn interval multiplier (bigger = calmer)
    bomb: float            # bomb weight multiplier
    size: float            # balloon size multiplier
    aim_assist: float      # hit-radius multiplier
    blurb: str


DIFFICULTIES = {
    "easy": Difficulty("easy", "Easy", 0.75, 1.30, 0.4, 1.20, 1.40, "Bigger balloons, aim assist"),
    "normal": Difficulty("normal", "Normal", 1.0, 1.0, 1.0, 1.0, 1.10, "The classic carnival"),
    "hard": Difficulty("hard", "Hard", 1.30, 0.75, 1.6, 0.85, 1.00, "Fast, small, lots of bombs"),
}
DIFFICULTY_ORDER = ["easy", "normal", "hard"]


@dataclass(frozen=True)
class Mode:
    key: str
    name: str
    tagline: str
    rules: tuple
    duration: float = 0.0      # seconds; 0 = untimed
    lives: int = 0             # 0 = no lives
    sky: str = "day"
    medals: tuple = field(default=(0, 0, 0))   # bronze, silver, gold score thresholds


MODES = {
    "time": Mode(
        "time", "Time Attack", "Score big before the clock runs out",
        ("60 seconds on the clock", "Clock balloons add +3s", "Bombs cost 5s and your combo"),
        duration=60.0, sky="day", medals=(1000, 2500, 4500)),
    "survival": Mode(
        "survival", "Survival", "Don't let them get away",
        ("Every escaped balloon costs a life", "Bombs cost 2 lives", "It only gets faster"),
        lives=10, sky="sunset", medals=(800, 2000, 4000)),
    "zen": Mode(
        "zen", "Zen", "No timer, no bombs, just pop",
        ("Relax and pop at your own pace", "No bombs, no fail", "Press Esc when you're done"),
        sky="dusk", medals=(500, 1500, 3000)),
}
MODE_ORDER = ["time", "survival", "zen"]

MEDAL_NAMES = ("Bronze", "Silver", "Gold")
MEDAL_COLORS = ((0.80, 0.50, 0.25), (0.78, 0.80, 0.85), (1.0, 0.80, 0.25))

# Sky palettes: zenith, horizon, sun colour, ambient, fog density
SKIES = {
    "day": dict(zenith=(0.16, 0.42, 0.88), horizon=(0.72, 0.84, 0.97), sun=(0.98, 0.90, 0.78),
                ambient=(0.50, 0.57, 0.72), sun_dir=(-0.45, 0.65, 0.62), stars=0.0),
    "sunset": dict(zenith=(0.20, 0.22, 0.55), horizon=(1.0, 0.62, 0.40), sun=(1.0, 0.70, 0.45),
                   ambient=(0.55, 0.45, 0.55), sun_dir=(0.35, 0.90, 0.18), stars=0.15),
    "dusk": dict(zenith=(0.10, 0.10, 0.30), horizon=(0.75, 0.50, 0.75), sun=(0.85, 0.75, 1.0),
                 ambient=(0.45, 0.42, 0.62), sun_dir=(-0.30, 0.85, 0.30), stars=0.8),
}
