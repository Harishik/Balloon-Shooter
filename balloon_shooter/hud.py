"""In-game HUD: score, combo meter, timer / lives, callouts, crosshair, overlays."""

import math

from direct.gui.DirectGui import DGG, DirectFrame
from panda3d.core import CardMaker, TransparencyAttrib

from . import config as C
from . import geometry as G
from .ui import GOLD, INK, INK_DIM, PINK


def _fmt_time(seconds):
    seconds = max(0, int(math.ceil(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


class Crosshair:
    def __init__(self, base, kit):
        self.base = base
        self.root = base.aspect2d.attachNewNode("crosshair")
        self.root.setBin("gui-popup", 100)
        ring_tex = G.ring_texture(128, 0.16)
        dot_tex = G.soft_dot_texture(32)
        cm = CardMaker("xh")
        cm.setFrame(-1, 1, -1, 1)
        self.ring = self.root.attachNewNode(cm.generate())
        self.ring.setTexture(ring_tex)
        self.ring.setScale(0.045)
        self.ring.setTransparency(TransparencyAttrib.MAlpha)
        self.dot = self.root.attachNewNode(cm.generate())
        self.dot.setTexture(dot_tex)
        self.dot.setScale(0.012)
        self.dot.setTransparency(TransparencyAttrib.MAlpha)
        # four ticks that flash on a hit
        self.ticks = self.root.attachNewNode("ticks")
        for ang in (45, 135, 225, 315):
            t = self.ticks.attachNewNode(CardMaker("tick").generate())
            t.setScale(0.006, 1, 0.026)
            t.setPos(-0.003, 0, 0.034)
            holder = self.ticks.attachNewNode("h")
            t.reparentTo(holder)
            holder.setR(ang)
        self.ticks.setColor(1, 1, 1, 1)
        self.ticks.setTransparency(TransparencyAttrib.MAlpha)
        self.kick = 0.0
        self.hit = 0.0
        self.color = (1, 1, 1)

    def set_pos(self, x, y):
        self.root.setPos(x, 0, y)

    def fire(self):
        self.kick = 1.0

    def hit_marker(self, bad=False):
        self.hit = 1.0
        self.ticks.setColor(*((1, 0.3, 0.25) if bad else (1, 1, 1)), 1)

    def set_target(self, kind_key):
        if kind_key == "bomb":
            self.color = (1.0, 0.35, 0.3)
        elif kind_key:
            self.color = (1.0, 0.9, 0.35)
        else:
            self.color = (1, 1, 1)

    def show(self, on=True):
        if on:
            self.root.show()
        else:
            self.root.hide()

    def update(self, dt):
        self.kick = max(0.0, self.kick - dt * 6)
        self.hit = max(0.0, self.hit - dt * 4)
        self.ring.setScale(0.045 * (1 + self.kick * 0.45))
        self.ring.setColor(*self.color, 0.95)
        self.dot.setColor(*self.color, 1)
        self.ticks.setScale(1 + (1 - self.hit) * 0.4)
        self.ticks.setAlphaScale(self.hit)


class Callout:
    """Big centre-screen text that punches in and fades."""

    def __init__(self, kit, parent):
        self.text = kit.label(parent, "", pos=(0, 0.25), scale=0.14, color=GOLD)
        self.t = 9.0
        self.life = 1.0

    def show(self, text, color=GOLD, life=1.0, y=0.25, scale=0.14):
        self.text.setText(text)
        self.text.setFg(color)
        self.text.setPos(0, y)
        self.base_scale = scale
        self.t = 0.0
        self.life = life

    def update(self, dt):
        self.t += dt
        k = self.t / self.life
        if k >= 1:
            self.text.hide()
            return
        self.text.show()
        if k < 0.12:
            s = (k / 0.12) * 1.3
        elif k < 0.25:
            s = 1.3 - (k - 0.12) / 0.13 * 0.3
        else:
            s = 1.0
        self.text.setScale(self.base_scale * max(0.01, s))
        self.text.setAlphaScale(1.0 if k < 0.7 else max(0.0, 1 - (k - 0.7) / 0.3))


class HUD:
    def __init__(self, base, kit):
        self.base = base
        self.kit = kit
        self.root = base.aspect2d.attachNewNode("hud")
        self.crosshair = Crosshair(base, kit)

        self._anchors = []

        # score panel (top-left)
        self.score_root = self._anchor("tl")
        kit.panel(self.score_root, 0.62, 0.36, pos=(0.36, -0.23))
        kit.label(self.score_root, "SCORE", pos=(0.1, -0.12), scale=0.04, align="left", color=INK_DIM)
        self.score_text = kit.label(self.score_root, "0", pos=(0.1, -0.235), scale=0.095, align="left")
        self.combo_bar_bg = DirectFrame(parent=self.score_root, frameSize=(0, 0.42, -0.012, 0.012),
                                        frameColor=(1, 1, 1, 0.15), pos=(0.1, 0, -0.30), relief=DGG.FLAT)
        self.combo_bar = DirectFrame(parent=self.score_root, frameSize=(0, 0.42, -0.012, 0.012),
                                     frameColor=GOLD, pos=(0.1, 0, -0.30), relief=DGG.FLAT)
        self.combo_text = kit.label(self.score_root, "", pos=(0.62, -0.235), scale=0.075, align="right",
                                    color=GOLD)
        self.chain_text = kit.label(self.score_root, "", pos=(0.1, -0.36), scale=0.04, align="left",
                                    color=INK_DIM)

        # centre top: timer / lives / zen clock
        self.top_root = self._anchor("tc")
        self.top_panel = kit.panel(self.top_root, 0.52, 0.17, pos=(0, -0.12))
        self.top_label = kit.label(self.top_root, "", pos=(0, -0.145), scale=0.085)
        self.lives_root = self.top_root.attachNewNode("lives")
        self.lives_dots = []

        # best score (top-right)
        self.best_root = self._anchor("tr")
        kit.panel(self.best_root, 0.44, 0.17, pos=(-0.26, -0.12))
        kit.label(self.best_root, "BEST", pos=(-0.43, -0.135), scale=0.04, align="left", color=INK_DIM)
        self.best_text = kit.label(self.best_root, "0", pos=(-0.09, -0.145), scale=0.06, align="right",
                                   color=GOLD)

        # power-up bar (bottom-centre)
        self.power_root = self._anchor("bc")
        self.power_label = kit.label(self.power_root, "SLOW-MO", pos=(0, 0.17), scale=0.05,
                                     color=(0.7, 0.95, 1, 1))
        DirectFrame(parent=self.power_root, frameSize=(-0.3, 0.3, -0.014, 0.014), frameColor=(1, 1, 1, 0.18),
                    pos=(0, 0, 0.13), relief=DGG.FLAT)
        self.power_bar = DirectFrame(parent=self.power_root, frameSize=(-0.3, 0.3, -0.014, 0.014),
                                     frameColor=(0.6, 0.92, 1, 1), pos=(0, 0, 0.13), relief=DGG.FLAT)
        self.power_root.hide()

        self.callout = Callout(kit, self.root)
        self.sub_callout = Callout(kit, self.root)
        self.hint = kit.label(self.root, "", pos=(0, -0.62), scale=0.05, color=INK_DIM)

        # full-screen overlay used for flashes when post-processing is off
        cm = CardMaker("overlay")
        cm.setFrameFullscreenQuad()
        self.overlay = base.render2d.attachNewNode(cm.generate())
        self.overlay.setTransparency(TransparencyAttrib.MAlpha)
        self.overlay.setColor(1, 1, 1, 0)
        self.overlay.setBin("fixed", 0)
        self.overlay_alpha = 0.0
        self.overlay_col = (1, 1, 1)
        self.vignette = None

        self.shown_score = 0.0
        self.target_score = 0
        self.score_punch = 0.0
        self.time_pulse = 0.0
        self.hide()

    def _anchor(self, where):
        parent = {"tl": self.base.a2dTopLeft, "tc": self.base.a2dTopCenter, "tr": self.base.a2dTopRight,
                  "bc": self.base.a2dBottomCenter}[where]
        node = parent.attachNewNode(f"hud-{where}")
        self._anchors.append(node)
        return node

    # -- visibility ----------------------------------------------------------------
    def show(self):
        self.root.show()
        for a in self._anchors:
            a.show()
        self.crosshair.show(True)

    def hide(self):
        self.root.hide()
        for a in self._anchors:
            a.hide()
        self.crosshair.show(False)

    # -- setup for a new run -------------------------------------------------------
    def setup(self, session, best):
        self.shown_score = 0.0
        self.target_score = 0
        self.best_text.setText(f"{best:,}" if best else "-")
        for d in self.lives_dots:
            d.destroy()
        self.lives_dots = []
        if session.has_lives:
            self.top_label.hide()
            n = session.mode.lives
            spacing = 0.05
            for i in range(n):
                d = self.kit.dot(self.lives_root, (1.0, 0.36, 0.45, 1), 0.04,
                                 pos=((i - (n - 1) / 2) * spacing, -0.12))
                self.lives_dots.append(d)
        else:
            self.top_label.show()
        self.power_root.hide()
        self.hint.setText("")

    # -- events ------------------------------------------------------------------
    def big(self, text, color=GOLD, life=1.0):
        self.callout.show(text, color, life)

    def small(self, text, color=INK, life=1.1):
        self.sub_callout.show(text, color, life, y=0.12, scale=0.075)

    def flash(self, color=(1, 1, 1), amount=0.5):
        self.overlay_col = color
        self.overlay_alpha = amount

    def punch_score(self):
        self.score_punch = 1.0

    # -- per frame ---------------------------------------------------------------
    def update(self, dt, session):
        self.crosshair.update(dt)
        self.callout.update(dt)
        self.sub_callout.update(dt)

        # score count-up
        self.target_score = session.score
        self.shown_score += (self.target_score - self.shown_score) * min(1.0, dt * 10)
        if abs(self.target_score - self.shown_score) < 1:
            self.shown_score = self.target_score
        self.score_text.setText(f"{int(round(self.shown_score)):,}")
        self.score_punch = max(0.0, self.score_punch - dt * 5)
        self.score_text.setScale(0.095 * (1 + 0.18 * self.score_punch))

        # combo
        mult = session.multiplier
        if session.chain:
            frac = max(0.0, session.combo_timer / C.COMBO_WINDOW)
            self.combo_bar.setScale(max(0.001, frac), 1, 1)
            self.combo_bar.show()
            self.combo_text.setText(f"x{mult}" if mult > 1 else "")
            self.chain_text.setText(f"{session.chain} combo")
        else:
            self.combo_bar.hide()
            self.combo_text.setText("")
            self.chain_text.setText("")

        # timer / lives / zen
        if session.timed:
            t = session.time_left
            self.top_label.setText(_fmt_time(t))
            if t <= 10 and not session.over:
                self.time_pulse += dt
                pulse = 0.5 + 0.5 * math.sin(self.time_pulse * 10)
                self.top_label.setFg((1, 0.35 + 0.4 * (1 - pulse), 0.3, 1))
                self.top_label.setScale(0.085 * (1 + 0.08 * pulse))
            else:
                self.top_label.setFg(INK)
                self.top_label.setScale(0.085)
        elif session.has_lives:
            for i, d in enumerate(self.lives_dots):
                d.setColorScale((1, 1, 1, 1) if i < session.lives else (0.3, 0.3, 0.4, 0.5))
        else:
            self.top_label.setText(f"ZEN  {_fmt_time(session.elapsed)}")
            self.top_label.setFg(PINK)

        if session.slowmo_left > 0:
            self.power_root.show()
            self.power_bar.setScale(max(0.001, session.slowmo_left / C.SLOWMO_DURATION), 1, 1)
        else:
            self.power_root.hide()

        self.overlay_alpha = max(0.0, self.overlay_alpha - dt * 3)
        self.overlay.setColor(*self.overlay_col, self.overlay_alpha)
