"""Pure game rules: scoring, combos, lives, timers and spawn pacing.

The 3D layer feeds this module shots, pops and escapes and reacts to the
events it returns. Keeping the rules engine-free makes them easy to test.
"""

import random
from dataclasses import dataclass, field

from . import config as C


@dataclass
class PopResult:
    points: int = 0
    multiplier: int = 1
    callout: str = ""
    events: list = field(default_factory=list)


class Session:
    """State for a single run of one mode at one difficulty."""

    def __init__(self, mode_key="time", difficulty_key="normal", seed=None):
        self.mode = C.MODES[mode_key]
        self.difficulty = C.DIFFICULTIES[difficulty_key]
        self.rng = random.Random(seed)

        self.score = 0
        self.shots = 0
        self.hits = 0
        self.popped = 0
        self.popped_by_kind = {}
        self.escaped = 0
        self.chain = 0
        self.best_chain = 0
        self.combo_timer = 0.0
        self.elapsed = 0.0
        self.time_left = self.mode.duration
        self.lives = self.mode.lives
        self.slowmo_left = 0.0
        self.clocks_collected = 0
        self.over = False
        self._spawn_clock = 0.6     # first balloon arrives quickly

    # -- derived values -------------------------------------------------------
    @property
    def timed(self):
        return self.mode.duration > 0

    @property
    def has_lives(self):
        return self.mode.lives > 0

    @property
    def multiplier(self):
        return min(C.COMBO_MAX_MULT, 1 + self.chain // C.COMBO_STEP)

    @property
    def accuracy(self):
        return 100.0 * self.hits / self.shots if self.shots else 0.0

    @property
    def time_scale(self):
        return C.SLOWMO_SCALE if self.slowmo_left > 0 else 1.0

    @property
    def intensity(self):
        """Difficulty ramp: starts at 1 and grows the longer you survive."""
        if self.mode.key == "time":
            return 1.0 + 0.6 * min(1.0, self.elapsed / max(1.0, self.mode.duration))
        if self.mode.key == "survival":
            return min(2.4, 1.0 + self.elapsed / 75.0)
        return min(1.25, 1.0 + self.elapsed / 300.0)

    def speed_scale(self):
        return self.difficulty.speed * (0.85 + 0.35 * self.intensity)

    def spawn_interval(self):
        base = 0.62 if self.mode.key != "zen" else 0.8
        return base * self.difficulty.spawn / self.intensity

    def medal(self):
        """Index of the medal earned (0 bronze .. 2 gold) or -1 for none."""
        earned = -1
        for i, threshold in enumerate(self.mode.medals):
            if self.score >= threshold:
                earned = i
        return earned

    # -- spawning -----------------------------------------------------------
    def kind_weights(self):
        weights = {}
        late = self.intensity - 1.0
        for key, w in C.SPAWN_WEIGHTS.items():
            if self.mode.key not in C.KINDS[key].modes:
                continue
            if key == "bomb":
                w *= self.difficulty.bomb * (1.0 + 0.8 * late)
            elif key == "swift":
                w *= 1.0 + 1.2 * late
            elif key == "armored":
                w *= 1.0 + 0.8 * late
            elif key == "heart" and self.lives >= self.mode.lives:
                continue
            elif key == "clock":
                # clocks are a comeback tool, and get rarer the more you collect
                if self.time_left > C.CLOCK_MAX_TIME:
                    continue
                w /= 1.0 + self.clocks_collected * 0.5
            weights[key] = w
        return weights

    def pick_kind(self):
        weights = self.kind_weights()
        keys = list(weights)
        return self.rng.choices(keys, weights=[weights[k] for k in keys])[0]

    def due_spawns(self, dt_world):
        """Advance the spawn clock and return how many balloons to spawn now."""
        if self.over:
            return 0
        self._spawn_clock -= dt_world
        count = 0
        while self._spawn_clock <= 0:
            interval = self.spawn_interval()
            self._spawn_clock += interval * self.rng.uniform(0.7, 1.3)
            count += 1
        return count

    # -- time -----------------------------------------------------------------
    def update(self, dt):
        """Advance real time. Returns a list of event tuples."""
        events = []
        if self.over:
            return events
        self.elapsed += dt
        if self.slowmo_left > 0:
            self.slowmo_left = max(0.0, self.slowmo_left - dt)
            if self.slowmo_left == 0:
                events.append(("slowmo_end",))
        if self.chain:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self._break_chain(events)
        if self.timed:
            self.time_left = max(0.0, self.time_left - dt)
            if self.time_left == 0:
                self._end(events)
        return events

    # -- player actions ------------------------------------------------------
    def register_shot(self, hit):
        """Record a trigger pull. Returns events (a miss may break the combo)."""
        events = []
        if self.over:
            return events
        self.shots += 1
        if hit:
            self.hits += 1
        elif self.chain and self.mode.key != "zen":
            self._break_chain(events)
        return events

    def chip(self):
        """A non-lethal hit on an armored balloon. Returns the points earned."""
        if self.over:
            return 0
        self._extend_chain([])
        points = 5 * self.multiplier
        self.score += points
        return points

    def pop(self, kind_key, by_blast=False):
        """A balloon was popped. Returns the points earned and any events."""
        result = PopResult()
        if self.over:
            return result
        kind = C.KINDS[kind_key]

        if kind_key == "bomb":
            if by_blast:
                result.events.append(("defused",))
                return result
            self.score = max(0, self.score + kind.points)
            result.points = kind.points
            self._break_chain(result.events)
            if self.timed:
                self.time_left = max(0.0, self.time_left - 5.0)
                result.events.append(("time_penalty", 5.0))
                if self.time_left == 0:
                    self._end(result.events)
            if self.has_lives:
                self._lose_lives(2, result.events)
            result.events.append(("bomb",))
            return result

        self.popped += 1
        self.popped_by_kind[kind_key] = self.popped_by_kind.get(kind_key, 0) + 1
        result.callout = self._extend_chain(result.events)
        result.multiplier = self.multiplier
        result.points = kind.points * result.multiplier
        self.score += result.points

        if kind_key == "frost":
            self.slowmo_left = C.SLOWMO_DURATION
            result.events.append(("slowmo",))
        elif kind_key == "nova":
            result.events.append(("nova",))
        elif kind_key == "clock" and self.timed:
            self.time_left += C.CLOCK_BONUS
            self.clocks_collected += 1
            result.events.append(("time_bonus", C.CLOCK_BONUS))
        elif kind_key == "heart" and self.has_lives:
            if self.lives < self.mode.lives:
                self.lives += 1
                result.events.append(("life_gained",))
        elif kind_key == "gold":
            result.events.append(("gold",))
        return result

    def escape(self, kind_key):
        """A balloon floated off the top of the screen."""
        events = []
        if self.over or kind_key == "bomb":
            return events
        self.escaped += 1
        if self.has_lives and kind_key not in ("heart",):
            self._lose_lives(1, events)
        return events

    def quit(self):
        """End an untimed run voluntarily (Zen mode)."""
        events = []
        self._end(events)
        return events

    # -- internals ------------------------------------------------------------
    def _extend_chain(self, events):
        before = self.multiplier
        self.chain += 1
        self.best_chain = max(self.best_chain, self.chain)
        self.combo_timer = C.COMBO_WINDOW
        if self.multiplier > before:
            events.append(("multiplier", self.multiplier))
        return C.STREAK_CALLOUTS.get(self.chain, "")

    def _break_chain(self, events):
        if self.chain >= C.COMBO_STEP:
            events.append(("combo_lost", self.chain))
        self.chain = 0
        self.combo_timer = 0.0

    def _lose_lives(self, n, events):
        self.lives = max(0, self.lives - n)
        events.append(("life_lost", n))
        if self.lives == 0:
            self._end(events)

    def _end(self, events):
        if not self.over:
            self.over = True
            self.slowmo_left = 0.0
            events.append(("game_over",))
