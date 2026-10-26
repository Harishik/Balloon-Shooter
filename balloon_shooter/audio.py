"""Sound effects and music with simple volume buses."""

import os
import random

from panda3d.core import Filename

SOUND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")

SFX = ["pop1", "pop2", "pop3", "shoot", "clank", "bomb", "gold", "bonus", "powerup", "freeze", "nova",
       "blip", "hover", "click", "count", "go", "escape", "lose", "gameover", "newbest"]
MUSIC = ["music_carnival", "music_zen"]
# Frequently overlapping sounds get several voices so they don't cut each other off.
VOICES = {"pop1": 3, "pop2": 3, "pop3": 3, "shoot": 4, "clank": 2, "blip": 2, "hover": 2}


class Audio:
    def __init__(self, base, settings):
        self.base = base
        self.settings = settings
        self.sfx = {}
        self.music = {}
        self.current = None
        self.current_name = None
        self.muted = False
        self._rate = 1.0
        self._next = {}
        for name in SFX:
            voices = VOICES.get(name, 1)
            sounds = [self._load(base.loader.loadSfx, name) for _ in range(voices)]
            self.sfx[name] = [s for s in sounds if s]
            self._next[name] = 0
        for name in MUSIC:
            m = self._load(base.loader.loadMusic, name)
            if m:
                m.setLoop(True)
            self.music[name] = m

    @staticmethod
    def _load(loader, name):
        path = Filename.fromOsSpecific(os.path.join(SOUND_DIR, name + ".wav"))
        try:
            return loader(path)
        except Exception:   # audio is optional: a missing file must not crash the game
            return None

    def _sfx_level(self):
        return 0.0 if self.muted else self.settings.master_volume * self.settings.sfx_volume

    def _music_level(self):
        return 0.0 if self.muted else self.settings.master_volume * self.settings.music_volume

    def play(self, name, volume=1.0, rate=1.0):
        voices = self.sfx.get(name)
        if not voices:
            return
        i = self._next[name]
        self._next[name] = (i + 1) % len(voices)
        s = voices[i]
        s.setVolume(volume * self._sfx_level())
        s.setPlayRate(rate)
        s.play()

    def pop(self, big=False):
        name = random.choice(("pop1", "pop2", "pop3"))
        self.play(name, 1.0, random.uniform(0.75, 0.9) if big else random.uniform(0.9, 1.15))

    def play_music(self, name):
        if name == self.current_name:
            return
        if self.current:
            self.current.stop()
        self.current = self.music.get(name)
        self.current_name = name
        if self.current:
            self.current.setVolume(self._music_level())
            self.current.setPlayRate(self._rate)
            self.current.play()

    def set_music_rate(self, rate):
        self._rate = rate
        if self.current:
            self.current.setPlayRate(rate)

    def toggle_mute(self):
        self.muted = not self.muted
        self.refresh()

    def refresh(self):
        if self.current:
            self.current.setVolume(self._music_level())
