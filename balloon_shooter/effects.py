"""Juice: confetti bursts, shockwaves, sparkles, tracers, floating score text
and the player's blaster."""

import math
import random

from panda3d.core import CardMaker, LineSegs, NodePath, TextNode, TransparencyAttrib, Vec3, Vec4

from . import geometry as G
from . import shaders
from .world import additive


def _card(name, size=1.0):
    cm = CardMaker(name)
    cm.setFrame(-size / 2, size / 2, -size / 2, size / 2)
    return NodePath(cm.generate())


class Effects:
    def __init__(self, base, font=None):
        self.base = base
        self.root = base.render.attachNewNode("fx")
        self.font = font
        self.rng = random.Random()
        self.items = []          # [node, update_fn, state]
        self._sprite_shader = shaders.sprite()
        self._lit = shaders.lit()
        self.tex_dot = G.soft_dot_texture()
        self.tex_ring = G.ring_texture()
        self.tex_star = G.star_texture()

        self._confetti = G.box(0.22, 0.02, 0.13, (1, 1, 1, 1), name="confetti")
        self._shred = self._make_shred()
        self._sprite_card = _card("sprite")

    def _make_shred(self):
        mb = G.MeshBuilder("shred")
        pts = [(0, 0, 0), (0.35, 0, 0.05), (0.28, 0, 0.3), (0.05, 0, 0.22)]
        c = (1, 1, 1, 1)
        mb.flat_tri(pts[0], pts[1], pts[2], c)
        mb.flat_tri(pts[0], pts[2], pts[3], c)
        node = mb.node()
        node.setTwoSided(True)
        return node

    # -- primitives ---------------------------------------------------------------
    def _sprite(self, tex, pos, color, scale):
        s = self._sprite_card.copyTo(self.root)
        s.setTexture(tex)
        s.setShader(self._sprite_shader)
        s.setShaderInput("u_tint", Vec4(*color))
        s.setPos(pos)
        s.setScale(scale)
        s.setBillboardPointEye()
        additive(s)
        return s

    def _add(self, node, fn, **state):
        state.setdefault("t", 0.0)
        self.items.append([node, fn, state])

    # -- effects ------------------------------------------------------------------------
    def pop(self, pos, color, size=1.0, amount=26, big=False):
        rnd = self.rng
        pos = Vec3(pos)
        palette = [color, tuple(min(1, c * 1.3 + 0.15) for c in color), (1, 1, 1)]
        for _ in range(amount):
            node = self._confetti.copyTo(self.root)
            node.setShader(self._lit)
            col = rnd.choice(palette)
            node.setShaderInput("u_tint", Vec4(*col, 1))
            node.setPos(pos + Vec3(rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4)) * size)
            node.setHpr(rnd.uniform(0, 360), rnd.uniform(0, 360), rnd.uniform(0, 360))
            speed = rnd.uniform(4, 11) * (1.5 if big else 1.0) * size
            a = rnd.uniform(0, math.tau)
            e = rnd.uniform(-0.6, 1.2)
            vel = Vec3(math.cos(a) * math.cos(e), math.sin(a) * math.cos(e) * 0.6, math.sin(e) + 0.4) * speed
            spin = Vec3(rnd.uniform(-720, 720), rnd.uniform(-720, 720), rnd.uniform(-720, 720))
            node.setScale(size * rnd.uniform(0.7, 1.4))
            self._add(node, self._update_debris, vel=vel, spin=spin, life=rnd.uniform(1.0, 1.8), col=col,
                      drag=2.2, grav=9.0)
        # rubber shreds of the balloon itself
        for _ in range(5 if size < 1.4 else 8):
            node = self._shred.copyTo(self.root)
            node.setShader(self._lit)
            node.setShaderInput("u_tint", Vec4(*color, 1))
            node.setPos(pos)
            node.setScale(size * rnd.uniform(1.2, 2.0))
            node.setHpr(rnd.uniform(0, 360), rnd.uniform(0, 360), 0)
            a = rnd.uniform(0, math.tau)
            vel = Vec3(math.cos(a) * 5, math.sin(a) * 2, rnd.uniform(1, 5)) * size
            spin = Vec3(rnd.uniform(-400, 400), rnd.uniform(-400, 400), 0)
            self._add(node, self._update_debris, vel=vel, spin=spin, life=rnd.uniform(0.8, 1.3), col=color,
                      drag=3.0, grav=12.0)
        # flash + ring
        flash = self._sprite(self.tex_star, pos, (1, 1, 0.95, 1), 2.2 * size)
        self._add(flash, self._update_flash, life=0.18, scale=2.2 * size * (1.6 if big else 1.0))
        ring = self._sprite(self.tex_ring, pos, (*color, 1), 0.5 * size)
        self._add(ring, self._update_ring, life=0.35, scale=(4.0 if not big else 9.0) * size, col=color)

    def sparkle_trail(self, pos, color):
        s = self._sprite(self.tex_dot, Vec3(pos), (*color, 0.9), 0.6)
        self._add(s, self._update_flash, life=0.5, scale=0.6)

    def shockwave(self, pos, color, radius):
        ring = self._sprite(self.tex_ring, Vec3(pos), (*color, 1), 1.0)
        self._add(ring, self._update_ring, life=0.55, scale=radius * 2.3, col=color)
        glow = self._sprite(self.tex_dot, Vec3(pos), (*color, 1), radius)
        self._add(glow, self._update_flash, life=0.4, scale=radius * 2.0)

    def tracer(self, start, end, color=(1.0, 0.95, 0.6)):
        ls = LineSegs("tracer")
        ls.setThickness(3.0)
        ls.setColor(*color, 1)
        ls.moveTo(start)
        ls.drawTo(end)
        node = self.root.attachNewNode(ls.create())
        additive(node)
        node.setTransparency(TransparencyAttrib.MAlpha)
        self._add(node, self._update_fade, life=0.09)
        tip = self._sprite(self.tex_dot, Vec3(end), (*color, 1), 0.7)
        self._add(tip, self._update_flash, life=0.12, scale=0.9)

    def popup(self, pos, text, color=(1, 1, 1, 1), scale=1.0):
        tn = TextNode("popup")
        tn.setText(text)
        if self.font:
            tn.setFont(self.font)
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(*color)
        tn.setShadow(0.06, 0.06)
        tn.setShadowColor(0, 0, 0, 0.55)
        node = self.root.attachNewNode(tn)
        node.setPos(Vec3(pos) + Vec3(0, -1.0, 0.8))
        node.setBillboardPointEye()
        node.setScale(0.01)
        node.setDepthTest(False)
        node.setDepthWrite(False)
        node.setBin("fixed", 50)
        node.setLightOff()
        node.setTransparency(TransparencyAttrib.MAlpha)
        dist = max(1.0, Vec3(pos).length())
        self._add(node, self._update_popup, life=1.0, scale=scale * dist * 0.048)

    # -- updaters (return False when finished) ------------------------------------
    def _update_debris(self, node, s, dt):
        s["vel"] *= max(0.0, 1.0 - s["drag"] * dt)
        s["vel"].z -= s["grav"] * dt
        node.setPos(node.getPos() + s["vel"] * dt)
        node.setHpr(node.getHpr() + s["spin"] * dt)
        k = s["t"] / s["life"]
        if k > 0.7:
            node.setShaderInput("u_tint", Vec4(*s["col"], 1))
            node.setScale(node.getScale() * (1 - dt * 3))
        return k < 1

    def _update_flash(self, node, s, dt):
        k = s["t"] / s["life"]
        node.setScale(s["scale"] * (0.6 + 0.8 * k))
        node.setAlphaScale(max(0.0, 1 - k))
        node.setColorScale(1, 1, 1, max(0.0, 1 - k))
        return k < 1

    def _update_ring(self, node, s, dt):
        k = s["t"] / s["life"]
        e = 1 - (1 - k) ** 3
        node.setScale(0.3 + s["scale"] * e)
        node.setColorScale(1, 1, 1, max(0.0, 1 - k) ** 1.5)
        return k < 1

    def _update_fade(self, node, s, dt):
        k = s["t"] / s["life"]
        node.setColorScale(1, 1, 1, max(0.0, 1 - k))
        return k < 1

    def _update_popup(self, node, s, dt):
        k = s["t"] / s["life"]
        if k < 0.15:
            sc = s["scale"] * (k / 0.15) * 1.25
        elif k < 0.3:
            sc = s["scale"] * (1.25 - (k - 0.15) / 0.15 * 0.25)
        else:
            sc = s["scale"]
        node.setScale(max(0.001, sc))
        node.setZ(node.getZ() + dt * 2.2 * (1 - k))
        node.setColorScale(1, 1, 1, 1 if k < 0.6 else max(0.0, 1 - (k - 0.6) / 0.4))
        return k < 1

    # -- loop -----------------------------------------------------------------------
    def update(self, dt):
        keep = []
        for item in self.items:
            node, fn, state = item
            state["t"] += dt
            if fn(node, state, dt):
                keep.append(item)
            else:
                node.removeNode()
        self.items = keep

    def clear(self):
        for node, _, _ in self.items:
            node.removeNode()
        self.items = []


class Blaster:
    """A chunky toy blaster held in the bottom-right of the view."""

    def __init__(self, base, parent):
        self.base = base
        self.root = parent.attachNewNode("blaster-rig")
        self.rest = Vec3(0.62, 1.55, -0.62)
        self.root.setPos(self.rest)
        self.root.setScale(0.42)
        self.model = self.root.attachNewNode("blaster")
        self.model.setShader(shaders.lit())
        teal = (0.12, 0.70, 0.80, 1)
        teal_dark = (0.08, 0.48, 0.58, 1)
        orange = (1.0, 0.56, 0.16, 1)
        cream = (0.98, 0.94, 0.85, 1)
        dark = (0.20, 0.22, 0.30, 1)
        pink = (1.0, 0.40, 0.65, 1)
        body = G.box(0.34, 1.0, 0.32, teal)
        body.reparentTo(self.model)
        stripe = G.box(0.35, 0.5, 0.08, cream)
        stripe.reparentTo(self.model)
        stripe.setPos(0, 0.1, 0.04)
        rear = G.box(0.30, 0.25, 0.26, teal_dark)
        rear.reparentTo(self.model)
        rear.setPos(0, -0.6, -0.02)
        barrel = G.cylinder(0.10, 0.9, 16, orange)
        barrel.reparentTo(self.model)
        barrel.setPos(0, 0.45, 0.04)
        for k in range(3):
            fin = G.cylinder(0.125, 0.06, 16, cream)
            fin.reparentTo(self.model)
            fin.setPos(0, 0.65 + k * 0.18, 0.04)
        muzzle = G.cylinder(0.12, 0.16, 16, dark, radius_top=0.16)
        muzzle.reparentTo(self.model)
        muzzle.setPos(0, 1.35, 0.04)
        tank = G.ico_sphere(2, pink)
        tank.reparentTo(self.model)
        tank.setPos(0, -0.12, 0.30)
        tank.setScale(0.19, 0.24, 0.19)
        cap = G.cylinder(0.06, 0.08, 10, cream)
        cap.setP(90)
        cap.reparentTo(self.model)
        cap.setPos(0, -0.12, 0.46)
        grip = G.box(0.2, 0.24, 0.4, dark)
        grip.reparentTo(self.model)
        grip.setPos(0, -0.32, -0.3)
        grip.setP(-18)
        self.model.flattenStrong()
        self.muzzle = self.model.attachNewNode("muzzle")
        self.muzzle.setPos(0, 1.55, 0.04)
        self.kick = 0.0
        self.bob = 0.0
        self.aim_h = 0.0
        self.aim_p = 0.0

    def fire(self):
        self.kick = 1.0

    def muzzle_world(self):
        return self.muzzle.getPos(self.base.render)

    def update(self, dt, aim_film, tan_half=(1.0, 0.55)):
        self.bob += dt
        # Point the barrel at the spot under the crosshair. A short convergence
        # distance angles the gun inwards so its side stays readable.
        depth = 9.0
        dx = aim_film[0] * tan_half[0] * depth - self.rest.x
        dy = depth - self.rest.y
        dz = aim_film[1] * tan_half[1] * depth - self.rest.z
        # never swing far right, or the gun turns its back on the camera
        target_h = max(-4.0, min(35.0, -math.degrees(math.atan2(dx, dy))))
        target_p = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        k = min(1.0, dt * 14)
        self.aim_h += (target_h - self.aim_h) * k
        self.aim_p += (target_p - self.aim_p) * k
        self.kick = max(0.0, self.kick - dt * 7)
        kick = math.sin(self.kick * math.pi * 0.5) * self.kick
        self.model.setHpr(self.aim_h, self.aim_p + kick * 12, -10)
        self.model.setPos(0, -kick * 0.25, math.sin(self.bob * 1.6) * 0.015 + kick * 0.03)
