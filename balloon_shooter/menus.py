"""Menu screens: title, mode select, how-to-play, settings, pause and results."""

import math

from direct.gui.DirectGui import DGG, DirectFrame
from panda3d.core import TransparencyAttrib

from . import __version__
from . import config as C
from .ui import GOLD, INK_DIM, PINK, Stepper

TITLE_COLORS = [(1.0, 0.36, 0.42, 1), (1.0, 0.62, 0.22, 1), (1.0, 0.84, 0.26, 1), (0.42, 0.85, 0.42, 1),
                (0.30, 0.78, 0.95, 1), (0.66, 0.48, 1.0, 1), (1.0, 0.48, 0.78, 1)]


class Screen:
    """Base class: owns a root node, a focus list for keyboard navigation and a tick."""

    dim = 0.0

    def __init__(self, app):
        self.app = app
        self.kit = app.kit
        self.root = DirectFrame(parent=app.aspect2d, frameColor=(0, 0, 0, 0), frameSize=(-3, 3, -1, 1),
                                relief=DGG.FLAT)
        if self.dim:
            DirectFrame(parent=self.root, frameColor=(0.02, 0.02, 0.08, self.dim), frameSize=(-4, 4, -2, 2),
                        relief=DGG.FLAT, state=DGG.NORMAL)
        self.focusables = []
        self.focus = -1
        self.t = 0.0
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAlphaScale(0.0)

    def add(self, button):
        self.focusables.append(button)
        return button

    def nav(self, delta):
        if not self.focusables:
            return
        if 0 <= self.focus < len(self.focusables):
            self.kit._on_exit(self.focusables[self.focus])
        self.focus = (self.focus + delta) % len(self.focusables)
        self.kit._on_enter(self.focusables[self.focus])

    def activate(self):
        if 0 <= self.focus < len(self.focusables):
            b = self.focusables[self.focus]
            b.commandFunc(None)

    def back(self):
        pass

    def tick(self, dt):
        self.t += dt
        self.root.setAlphaScale(min(1.0, self.t * 5))

    def destroy(self):
        for b in self.focusables:
            self.kit.forget(b)
        self.root.destroy()


class TitleScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        kit = self.kit
        self.letters = []
        word = "BALLOON SHOOTER"
        spacing = 0.118
        x0 = -(len(word) - 1) * spacing / 2
        for i, ch in enumerate(word):
            if ch == " ":
                continue
            t = kit.label(self.root, ch, pos=(x0 + i * spacing, 0.52), scale=0.17,
                          color=TITLE_COLORS[i % len(TITLE_COLORS)])
            self.letters.append((t, i, x0 + i * spacing))
        badge = kit.panel(self.root, 0.5, 0.13, pos=(0.0, 0.31),
                          fill=((1.0, 0.84, 0.3, 1), (1.0, 0.6, 0.2, 1)), border=(1, 1, 1, 0.5))
        kit.label(badge, "3D", pos=(-0.15, -0.025), scale=0.075, color=(0.35, 0.15, 0.05, 1), shadow=False)
        kit.label(badge, "SKY CARNIVAL", pos=(0.07, -0.018), scale=0.035, color=(0.35, 0.15, 0.05, 1),
                  shadow=False)
        self.add(kit.button(self.root, "PLAY", app.show_mode_select, w=0.78, h=0.16, pos=(0, 0.05), scale=0.075))
        self.add(kit.button(self.root, "HOW TO PLAY", app.show_how_to, w=0.78, h=0.13, pos=(0, -0.13),
                            style="secondary", scale=0.058))
        self.add(kit.button(self.root, "SETTINGS", app.show_settings, w=0.78, h=0.13, pos=(0, -0.29),
                            style="secondary", scale=0.058))
        self.add(kit.button(self.root, "QUIT", app.quit, w=0.78, h=0.13, pos=(0, -0.45),
                            style="secondary", scale=0.058))
        prof = app.store.profile
        kit.label(self.root, f"Balloons popped: {prof.total_popped:,}    Games played: {prof.total_games:,}"
                             f"    Best combo: {prof.best_chain}",
                  pos=(0, -0.68), scale=0.04, color=INK_DIM, bold=False)
        kit.label(self.root, "Mouse to aim  -  Click to pop  -  Esc to pause  -  M to mute",
                  pos=(0, -0.76), scale=0.036, color=INK_DIM, bold=False)
        kit.label(self.root, f"v{__version__}", pos=(0, -0.86), scale=0.03, color=INK_DIM, bold=False)

    def back(self):
        self.app.quit()

    def tick(self, dt):
        super().tick(dt)
        for t, i, x in self.letters:
            y = 0.52 + math.sin(self.t * 2.2 + i * 0.45) * 0.022
            t.setPos(x, y)
            t.setR(math.sin(self.t * 1.7 + i * 0.6) * 4)


class ModeSelect(Screen):
    def __init__(self, app):
        super().__init__(app)
        kit = self.kit
        settings = app.store.settings
        self.difficulty = settings.difficulty if settings.difficulty in C.DIFFICULTIES else "normal"
        kit.label(self.root, "CHOOSE YOUR GAME", pos=(0, 0.78), scale=0.09)
        self.cards = []
        accents = {"time": (1.0, 0.62, 0.22, 1), "survival": (1.0, 0.36, 0.42, 1), "zen": (0.66, 0.48, 1.0, 1)}
        for i, key in enumerate(C.MODE_ORDER):
            mode = C.MODES[key]
            x = (i - 1) * 0.86
            card = kit.panel(self.root, 0.8, 1.02, pos=(x, 0.13))
            kit.dot(card, accents[key], 0.16, pos=(0, 0.36))
            kit.label(card, mode.name.upper(), pos=(0, 0.21), scale=0.066)
            kit.label(card, mode.tagline, pos=(0, 0.13), scale=0.034, color=INK_DIM, bold=False)
            for j, rule in enumerate(mode.rules):
                kit.label(card, "-  " + rule, pos=(-0.34, 0.03 - j * 0.065), scale=0.032, align="left",
                          bold=False)
            best_label = kit.label(card, "", pos=(0, -0.24), scale=0.04, color=GOLD)
            btn = self.add(kit.button(card, "PLAY", self._start, w=0.56, h=0.12, pos=(0, -0.39), scale=0.06,
                                      extra_args=[key]))
            self.cards.append((key, best_label, btn))
        kit.label(self.root, "DIFFICULTY", pos=(0, -0.53), scale=0.045, color=INK_DIM)
        self.diff_buttons = {}
        for i, key in enumerate(C.DIFFICULTY_ORDER):
            d = C.DIFFICULTIES[key]
            b = kit.button(self.root, d.name.upper(), self._set_diff, w=0.36, h=0.11, pos=((i - 1) * 0.4, -0.63),
                           style="secondary", scale=0.05, extra_args=[key])
            self.diff_buttons[key] = self.add(b)
        self.diff_blurb = kit.label(self.root, "", pos=(0, -0.74), scale=0.036, color=INK_DIM, bold=False)
        self.add(kit.button(self.root, "BACK", self.back, w=0.32, h=0.1, pos=(0, -0.88), style="secondary",
                            scale=0.045))
        self._refresh()
        try:
            self.focus = C.MODE_ORDER.index(settings.last_mode) - 1
        except ValueError:
            self.focus = -1
        self.nav(1)

    def _set_diff(self, key):
        self.difficulty = key
        self.app.store.settings.difficulty = key
        self._refresh()

    def _refresh(self):
        prof = self.app.store.profile
        for key, label, _ in self.cards:
            best = prof.best_for(key, self.difficulty)
            medal = prof.medals.get(f"{key}:{self.difficulty}", -1)
            medal_txt = f"  {C.MEDAL_NAMES[medal]}" if medal >= 0 else ""
            label.setText(f"Best: {best:,}{medal_txt}" if best else "No score yet")
        for key, b in self.diff_buttons.items():
            self.kit.restyle(b, "selected" if key == self.difficulty else "secondary", 0.36, 0.11)
        self.diff_blurb.setText(C.DIFFICULTIES[self.difficulty].blurb)

    def _start(self, mode_key):
        self.app.store.settings.last_mode = mode_key
        self.app.start_game(mode_key, self.difficulty)

    def back(self):
        self.app.show_title()


class HowToScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        kit = self.kit
        kit.panel(self.root, 2.3, 1.62, pos=(0, 0.02))
        kit.label(self.root, "HOW TO PLAY", pos=(0, 0.7), scale=0.085)
        kit.label(self.root, "Aim with the mouse (or arrow keys / WASD) and click (or Space) to pop balloons. "
                             "Hold to keep firing.",
                  pos=(0, 0.59), scale=0.036, color=INK_DIM, bold=False)
        kit.label(self.root, "Chain hits for a combo multiplier up to x5. A miss or a bomb breaks the chain.",
                  pos=(0, 0.53), scale=0.036, color=INK_DIM, bold=False)
        keys = ["classic", "swift", "gold", "armored", "bomb", "frost", "nova", "clock", "heart"]
        for i, key in enumerate(keys):
            kind = C.KINDS[key]
            col, row = i % 3, i // 3
            x = -0.98 + col * 0.72
            y = 0.36 - row * 0.3
            color = kind.color if key != "classic" else C.CLASSIC_COLORS[0]
            kit.dot(self.root, (*color, 1), 0.13, pos=(x, y))
            kit.label(self.root, kind.name, pos=(x + 0.1, y + 0.015), scale=0.045, align="left")
            kit.label(self.root, kind.description, pos=(x + 0.1, y - 0.05), scale=0.031, align="left",
                      color=INK_DIM, bold=False)
        kit.label(self.root, "Esc / P  pause      M  mute      F11  fullscreen",
                  pos=(0, -0.52), scale=0.038, color=INK_DIM, bold=False)
        self.add(kit.button(self.root, "GOT IT", self.back, w=0.5, h=0.12, pos=(0, -0.66), scale=0.055))
        self.nav(1)

    def back(self):
        self.app.show_title()


class SettingsScreen(Screen):
    def __init__(self, app, on_back, dim=0.0):
        self.dim = dim
        super().__init__(app)
        self.on_back = on_back
        kit = self.kit
        s = app.store.settings
        kit.panel(self.root, 1.7, 1.55, pos=(0, 0.02))
        kit.label(self.root, "SETTINGS", pos=(0, 0.66), scale=0.085)
        pct = [i / 10 for i in range(11)]
        fmt_pct = lambda v: f"{int(round(v * 100))}%"
        on_off = lambda v: "On" if v else "Off"
        y = 0.48
        self.steppers = []

        def row(label, values, current, setter, fmt=str):
            nonlocal y
            idx = values.index(current) if current in values else 0
            st = Stepper(kit, self.root, label, values, idx, setter, pos=(0, y), fmt=fmt)
            self.steppers.append(st)
            self.add(st.left)
            self.add(st.right)
            y -= 0.14

        snap = lambda v: min(pct, key=lambda p: abs(p - v))
        row("Master volume", pct, snap(s.master_volume), lambda v: self._set("master_volume", v), fmt_pct)
        row("Music", pct, snap(s.music_volume), lambda v: self._set("music_volume", v), fmt_pct)
        row("Sound effects", pct, snap(s.sfx_volume), lambda v: self._set("sfx_volume", v), fmt_pct)
        row("Graphics", ["low", "high"], s.quality, lambda v: self._set("quality", v), str.capitalize)
        row("Screen shake", [False, True], s.screen_shake, lambda v: self._set("screen_shake", v), on_off)
        row("Fullscreen", [False, True], s.fullscreen, lambda v: self._set("fullscreen", v), on_off)
        row("Show FPS", [False, True], s.show_fps, lambda v: self._set("show_fps", v), on_off)
        self.note = kit.label(self.root, "", pos=(0, -0.5), scale=0.032, color=INK_DIM, bold=False)
        self.add(kit.button(self.root, "DONE", self.back, w=0.46, h=0.12, pos=(0, -0.62), scale=0.055))

    def _set(self, name, value):
        setattr(self.app.store.settings, name, value)
        if name == "quality":
            self.note.setText("Graphics changes apply on the next launch.")
        self.app.apply_settings()

    def back(self):
        self.app.store.save()
        self.on_back()


class PauseScreen(Screen):
    dim = 0.55

    def __init__(self, app):
        super().__init__(app)
        kit = self.kit
        kit.label(self.root, "PAUSED", pos=(0, 0.42), scale=0.13)
        self.add(kit.button(self.root, "RESUME", app.resume, w=0.7, h=0.14, pos=(0, 0.16), scale=0.065))
        self.add(kit.button(self.root, "RESTART", app.restart_run, w=0.7, h=0.12, pos=(0, 0.0), style="secondary",
                            scale=0.055))
        self.add(kit.button(self.root, "SETTINGS", app.show_pause_settings, w=0.7, h=0.12, pos=(0, -0.15),
                            style="secondary", scale=0.055))
        label = "END SESSION" if app.session and app.session.mode.key == "zen" else "QUIT TO MENU"
        self.add(kit.button(self.root, label, app.quit_to_menu, w=0.7, h=0.12, pos=(0, -0.3),
                            style="secondary", scale=0.055))
        self.nav(1)

    def back(self):
        self.app.resume()


class ResultsScreen(Screen):
    dim = 0.45

    def __init__(self, app, session, new_best, best):
        super().__init__(app)
        kit = self.kit
        self.session = session
        if session.mode.key == "time":
            heading = "TIME'S UP!"
        elif session.mode.key == "survival":
            heading = "GAME OVER"
        else:
            heading = "NICE SESSION!"
        kit.panel(self.root, 1.5, 1.62, pos=(0, 0.0))
        kit.label(self.root, heading, pos=(0, 0.66), scale=0.1)
        kit.label(self.root, f"{session.mode.name}  -  {session.difficulty.name}", pos=(0, 0.57), scale=0.04,
                  color=INK_DIM, bold=False)
        self.score_label = kit.label(self.root, "0", pos=(0, 0.36), scale=0.17, color=GOLD)
        self.shown = 0.0
        if new_best:
            self.best_label = kit.label(self.root, "NEW BEST!", pos=(0, 0.24), scale=0.06, color=PINK)
        else:
            self.best_label = kit.label(self.root, f"Best: {best:,}", pos=(0, 0.24), scale=0.045, color=INK_DIM)
        medal = session.medal()
        if medal >= 0:
            kit.dot(self.root, (*C.MEDAL_COLORS[medal], 1), 0.1, pos=(-0.2, 0.13))
            kit.label(self.root, f"{C.MEDAL_NAMES[medal]} medal", pos=(0.05, 0.115), scale=0.045,
                      color=(*C.MEDAL_COLORS[medal], 1))
        else:
            nxt = session.mode.medals[0]
            kit.label(self.root, f"Reach {nxt:,} for a Bronze medal", pos=(0, 0.115), scale=0.038,
                      color=INK_DIM, bold=False)
        mins, secs = divmod(int(session.elapsed), 60)
        stats = [("Balloons popped", f"{session.popped}"), ("Accuracy", f"{session.accuracy:.0f}%"),
                 ("Best combo", f"{session.best_chain}"), ("Time", f"{mins}:{secs:02d}")]
        for i, (k, v) in enumerate(stats):
            y = -0.02 - i * 0.085
            kit.label(self.root, k, pos=(-0.5, y), scale=0.045, align="left", color=INK_DIM, bold=False)
            kit.label(self.root, v, pos=(0.5, y), scale=0.05, align="right")
        self.add(kit.button(self.root, "PLAY AGAIN", app.restart_run, w=0.6, h=0.13, pos=(-0.33, -0.56), scale=0.055))
        self.add(kit.button(self.root, "MENU", app.quit_to_menu, w=0.56, h=0.13, pos=(0.33, -0.56),
                            style="secondary", scale=0.055))
        self.nav(1)

    def back(self):
        self.app.quit_to_menu()

    def tick(self, dt):
        super().tick(dt)
        target = self.session.score
        if self.t > 0.3:
            self.shown += max(1.0, (target - self.shown) * min(1.0, dt * 4))
            self.shown = min(self.shown, target)
        self.score_label.setText(f"{int(self.shown):,}")
        if self.shown >= target:
            pulse = 1 + 0.04 * math.sin(self.t * 4)
            self.score_label.setScale(0.17 * pulse)
