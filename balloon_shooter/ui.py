"""A small themed UI kit on top of DirectGUI: panels, buttons, labels, steppers."""

import os

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import ClockObject, Filename, TextNode, TransparencyAttrib

from . import geometry as G

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

# Theme
INK = (1, 1, 1, 1)
INK_DIM = (0.80, 0.84, 0.95, 1)
GOLD = (1.0, 0.84, 0.30, 1)
PINK = (1.0, 0.42, 0.55, 1)
PANEL = ((0.10, 0.12, 0.28, 0.86), (0.06, 0.07, 0.18, 0.90))
PANEL_BORDER = (1, 1, 1, 0.16)
SHADOW = (0.02, 0.02, 0.08, 0.6)

STYLES = {
    # name: (normal gradient, hover gradient, pressed gradient, border)
    "primary": (((1.0, 0.55, 0.35, 1), (0.95, 0.27, 0.45, 1)),
                ((1.0, 0.66, 0.45, 1), (1.0, 0.36, 0.55, 1)),
                ((0.85, 0.40, 0.28, 1), (0.78, 0.20, 0.36, 1)),
                (1, 1, 1, 0.35)),
    "secondary": (((0.26, 0.30, 0.55, 0.95), (0.18, 0.20, 0.42, 0.95)),
                  ((0.34, 0.40, 0.70, 0.98), (0.24, 0.27, 0.55, 0.98)),
                  ((0.16, 0.18, 0.36, 0.98), (0.12, 0.13, 0.30, 0.98)),
                  (1, 1, 1, 0.20)),
    "selected": (((1.0, 0.82, 0.30, 1), (1.0, 0.62, 0.18, 1)),
                 ((1.0, 0.88, 0.45, 1), (1.0, 0.70, 0.28, 1)),
                 ((0.90, 0.70, 0.22, 1), (0.85, 0.52, 0.12, 1)),
                 (1, 1, 1, 0.45)),
}


class Kit:
    def __init__(self, base, audio=None):
        self.base = base
        self.audio = audio
        self._tex = {}
        self.font_bold = self._font("Fredoka-Bold.ttf")
        self.font = self._font("Fredoka-Medium.ttf") or self.font_bold
        self._hover_items = {}
        base.taskMgr.add(self._animate, "ui-anim")

    def _font(self, name):
        path = Filename.fromOsSpecific(os.path.join(FONT_DIR, name))
        try:
            f = self.base.loader.loadFont(path)
        except Exception:
            return None
        if f is None or not f.isValid():
            return None
        f.setPixelsPerUnit(72)
        f.setPageSize(1024, 1024)
        return f

    # -- textures -----------------------------------------------------------------
    def tex(self, w, h, fill, border=None, radius=None, key=None):
        px_w, px_h = max(8, int(w * 240)), max(8, int(h * 240))
        r = radius if radius is not None else min(min(px_w, px_h) * 0.32, 34)
        k = key or (px_w, px_h, str(fill), str(border), r)
        if k not in self._tex:
            self._tex[k] = G.rounded_rect_texture(px_w, px_h, r, fill, border, 3 if border else 0)
        return self._tex[k]

    def circle_tex(self, color, px=48):
        return self.tex(px / 240, px / 240, color, radius=px / 2 - 0.5, key=("circle", str(color), px))

    # -- widgets -----------------------------------------------------------------
    def panel(self, parent, w, h, pos=(0, 0), fill=PANEL, border=PANEL_BORDER):
        f = DirectFrame(parent=parent, frameSize=(-w / 2, w / 2, -h / 2, h / 2),
                        frameTexture=self.tex(w, h, fill, border), frameColor=(1, 1, 1, 1),
                        pos=(pos[0], 0, pos[1]), relief=DGG.FLAT)
        f.setTransparency(TransparencyAttrib.MAlpha)
        return f

    def dot(self, parent, color, size, pos=(0, 0)):
        f = DirectFrame(parent=parent, frameSize=(-size / 2, size / 2, -size / 2, size / 2),
                        frameTexture=self.circle_tex(color), frameColor=(1, 1, 1, 1),
                        pos=(pos[0], 0, pos[1]), relief=DGG.FLAT)
        f.setTransparency(TransparencyAttrib.MAlpha)
        return f

    def label(self, parent, text, pos=(0, 0), scale=0.06, color=INK, align="center", bold=True, shadow=True):
        aligns = {"center": TextNode.ACenter, "left": TextNode.ALeft, "right": TextNode.ARight}
        t = OnscreenText(parent=parent, text=text, pos=pos, scale=scale, fg=color,
                         align=aligns[align], font=self.font_bold if bold else self.font,
                         shadow=SHADOW if shadow else None, shadowOffset=(0.06, 0.06), mayChange=True)
        return t

    def button(self, parent, text, command, w=0.7, h=0.15, pos=(0, 0), style="primary", scale=0.065,
               extra_args=None, sound=True):
        normal, hover, pressed, border = STYLES[style]
        textures = (self.tex(w, h, normal, border), self.tex(w, h, pressed, border),
                    self.tex(w, h, hover, border), self.tex(w, h, normal, border))

        def clicked(*args):
            if sound and self.audio:
                self.audio.play("click")
            command(*args)

        b = DirectButton(parent=parent, text=text, text_font=self.font_bold, text_scale=scale,
                         text_fg=INK, text_shadow=SHADOW, text_shadowOffset=(0.05, 0.05),
                         text_pos=(0, -scale * 0.35), frameSize=(-w / 2, w / 2, -h / 2, h / 2),
                         frameTexture=textures, frameColor=(1, 1, 1, 1), relief=DGG.FLAT,
                         pos=(pos[0], 0, pos[1]), command=clicked, extraArgs=extra_args or [],
                         pressEffect=False, rolloverSound=None, clickSound=None)
        b.setTransparency(TransparencyAttrib.MAlpha)
        b.bind(DGG.ENTER, self._on_enter, [b])
        b.bind(DGG.EXIT, self._on_exit, [b])
        self._hover_items[id(b)] = [b, 1.0, 1.0]
        return b

    def restyle(self, button, style, w, h):
        normal, hover, pressed, border = STYLES[style]
        button["frameTexture"] = (self.tex(w, h, normal, border), self.tex(w, h, pressed, border),
                                  self.tex(w, h, hover, border), self.tex(w, h, normal, border))

    def _on_enter(self, b, _evt=None):
        item = self._hover_items.get(id(b))
        if item:
            item[2] = 1.07
        if self.audio:
            self.audio.play("hover", 0.6)

    def _on_exit(self, b, _evt=None):
        item = self._hover_items.get(id(b))
        if item:
            item[2] = 1.0

    def forget(self, widget):
        self._hover_items.pop(id(widget), None)

    def _animate(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        dead = []
        for key, item in self._hover_items.items():
            b, cur, target = item
            if b.isEmpty():
                dead.append(key)
                continue
            cur += (target - cur) * min(1.0, dt * 16)
            item[1] = cur
            b.setScale(cur)
        for key in dead:
            del self._hover_items[key]
        return task.cont


class Stepper:
    """``<  value  >`` control used in Settings - friendlier than a slider."""

    def __init__(self, kit, parent, label, values, index, on_change, pos, fmt=str, width=1.5):
        self.values = values
        self.index = index
        self.on_change = on_change
        self.fmt = fmt
        y = pos[1]
        x = pos[0]
        self.title = kit.label(parent, label, pos=(x - width / 2, y - 0.02), scale=0.058, align="left",
                               color=INK_DIM)
        self.left = kit.button(parent, "<", self.step, w=0.12, h=0.11, pos=(x + width * 0.12, y),
                               style="secondary", scale=0.06, extra_args=[-1])
        self.value = kit.label(parent, "", pos=(x + width * 0.3, y - 0.02), scale=0.058)
        self.right = kit.button(parent, ">", self.step, w=0.12, h=0.11, pos=(x + width * 0.48, y),
                                style="secondary", scale=0.06, extra_args=[1])
        self._refresh()

    def step(self, delta):
        self.index = max(0, min(len(self.values) - 1, self.index + delta))
        self._refresh()
        self.on_change(self.values[self.index])

    def _refresh(self):
        self.value.setText(self.fmt(self.values[self.index]))
