"""Balloon entities and the field that spawns, moves and hit-tests them."""

import math
import random

from panda3d.core import Point2, Point3, Vec3, Vec4

from . import config as C
from . import geometry as G
from . import picking, shaders

# Per-kind look: metalness, pattern id (see BALLOON_FRAG), band colour + strength
LOOKS = {
    "classic": (0.0, 0, (1, 1, 1), 0.0),
    "swift": (0.25, 4, (0.75, 0.9, 1.0), 0.0),
    "gold": (0.9, 3, (1.0, 0.95, 0.7), 1.6),
    "armored": (1.0, 1, (0.35, 0.38, 0.45), 0.0),
    "bomb": (0.3, 1, (1.0, 0.18, 0.08), 2.2),
    "frost": (0.45, 1, (0.92, 1.0, 1.0), 1.0),
    "nova": (0.2, 2, (1.0, 0.65, 1.0), 1.3),
    "clock": (0.2, 1, (1.0, 1.0, 1.0), 0.9),
    "heart": (0.15, 4, (1.0, 0.85, 0.9), 0.0),
}

BASE_RADIUS = 1.25
STRETCH = 1.15


class Balloon:
    def __init__(self, field, kind_key, pos, speed, color, size):
        self.field = field
        self.kind = C.KINDS[kind_key]
        self.key = kind_key
        self.color = color
        self.radius = BASE_RADIUS * size
        self.hp = self.kind.hp
        self.alive = True
        self.speed = speed
        self.age = 0.0
        self.flash = 0.0
        self.squash = 0.0
        rnd = field.rng
        self.x0 = pos[0]
        self.phase = rnd.uniform(0, math.tau)
        self.freq = rnd.uniform(0.6, 1.1)
        self.amp = rnd.uniform(0.4, 1.1) * self.kind.wobble
        self.zig = rnd.choice((-1, 1)) * 3.5 if kind_key == "gold" else 0.0
        self.spin = rnd.uniform(-25, 25)

        self.node = field.root.attachNewNode(f"balloon-{kind_key}")
        self.node.setPos(*pos)
        self.body = field.mesh.instanceTo(self.node)
        self.body.setShader(field.shader)
        self.string = field.string.instanceTo(self.node)
        self.node.setScale(self.radius)
        metal, pattern, band, strength = LOOKS[kind_key]
        self.metal = metal
        self.pattern = pattern
        self.node.setShaderInput("u_color", Vec4(*color, 1))
        self.node.setShaderInput("u_band", Vec4(*band, strength))
        self._apply_params()

    def _apply_params(self):
        self.node.setShaderInput("u_params", Vec4(self.kind.glow, self.metal, self.flash, self.pattern))

    @property
    def pos(self):
        return self.node.getPos()

    def update(self, dt, wind):
        self.age += dt
        p = self.node.getPos()
        z = p.z + self.speed * dt
        if self.zig:
            self.x0 += self.zig * dt
            limit = self.field.half_width(p.y) * 0.85
            if abs(self.x0) > limit:
                self.zig = -self.zig
                self.x0 = math.copysign(limit, self.x0)
        else:
            self.x0 += wind * dt
        sway = math.sin(self.age * self.freq * 2.0 + self.phase) * self.amp
        self.node.setPos(self.x0 + sway, p.y, z)
        # lean into the sway, and spin slowly
        self.node.setR(math.cos(self.age * self.freq * 2.0 + self.phase) * 8.0 * self.kind.wobble)
        self.node.setH(self.node.getH() + self.spin * dt)
        if self.flash > 0 or self.squash > 0:
            self.flash = max(0.0, self.flash - dt * 6)
            self.squash = max(0.0, self.squash - dt * 5)
            s = self.radius
            k = math.sin(self.squash * math.pi) * 0.18
            self.node.setScale(s * (1 + k), s * (1 + k), s * (1 - k))
            self._apply_params()

    def damage(self):
        """Returns True if the balloon should pop."""
        self.hp -= 1
        if self.hp <= 0:
            return True
        self.flash = 1.0
        self.squash = 1.0
        # dented armour gets darker each hit
        k = self.hp / self.kind.hp
        self.color = tuple(c * (0.6 + 0.4 * k) for c in self.color)
        self.node.setShaderInput("u_color", Vec4(*self.color, 1))
        self.radius *= 0.92
        return False

    def destroy(self):
        self.alive = False
        self.node.removeNode()


class BalloonField:
    def __init__(self, base, seed=None):
        self.base = base
        self.root = base.render.attachNewNode("balloons")
        self.mesh = G.balloon_mesh()
        self.string = G.string_mesh()
        self.string.setShader(shaders.lit())
        self.shader = shaders.balloon()
        self.balloons = []
        self.rng = random.Random(seed)
        self.wind = 0.0
        self._wind_t = 0.0

    # -- view-frustum helpers -------------------------------------------------
    def _tan_half(self):
        lens = self.base.camLens
        fov = lens.getFov()
        return math.tan(math.radians(fov[0] / 2)), math.tan(math.radians(fov[1] / 2))

    def half_width(self, depth):
        return depth * self._tan_half()[0]

    def half_height(self, depth):
        return depth * self._tan_half()[1]

    def view_center_z(self):
        return self.base.camera.getZ()

    # -- lifecycle -------------------------------------------------------------
    def spawn(self, kind_key, speed_scale=1.0, size_scale=1.0, start_visible=False):
        kind = C.KINDS[kind_key]
        rnd = self.rng
        depth = rnd.uniform(C.NEAR_DEPTH, C.FAR_DEPTH)
        if kind_key in ("gold", "swift"):
            depth = rnd.uniform(C.NEAR_DEPTH + 4, C.FAR_DEPTH)
        hw = self.half_width(depth) * 0.82
        hh = self.half_height(depth)
        x = rnd.uniform(-hw, hw)
        if start_visible:
            z = self.view_center_z() + rnd.uniform(-hh, hh * 0.8)
        else:
            z = self.view_center_z() - hh - C.SPAWN_MARGIN - kind.size * 1.5
        # far balloons rise a touch faster so they cross the screen in similar time
        speed = rnd.uniform(2.8, 4.0) * kind.speed * speed_scale * (0.75 + 0.25 * depth / C.NEAR_DEPTH)
        color = rnd.choice(C.CLASSIC_COLORS) if kind_key == "classic" else kind.color
        b = Balloon(self, kind_key, (x, depth, z), speed, color, kind.size * size_scale)
        self.balloons.append(b)
        return b

    def update(self, dt):
        """Move balloons; returns the list of balloons that escaped this frame."""
        self._wind_t += dt
        self.wind = math.sin(self._wind_t * 0.15) * 0.6
        escaped = []
        top = self.view_center_z()
        for b in self.balloons:
            b.update(dt, self.wind)
            p = b.node.getPos()
            if p.z - b.radius * 1.2 > top + self.half_height(p.y) + C.ESCAPE_MARGIN:
                b.last_pos = p
                escaped.append(b)
        for b in escaped:
            self.remove(b)
        return escaped

    def remove(self, b):
        if b in self.balloons:
            self.balloons.remove(b)
        if b.alive:
            b.destroy()

    def clear(self):
        for b in list(self.balloons):
            self.remove(b)

    # -- shooting ----------------------------------------------------------------
    def ray_from_screen(self, film_xy):
        """World-space (origin, direction) for a point on the film (-1..1)."""
        near, far = Point3(), Point3()
        self.base.camLens.extrude(Point2(*film_xy), near, far)
        render = self.base.render
        near = render.getRelativePoint(self.base.cam, near)
        far = render.getRelativePoint(self.base.cam, far)
        d = Vec3(far - near)
        d.normalize()
        return near, d

    def pick(self, film_xy, assist=1.0):
        origin, d = self.ray_from_screen(film_xy)
        targets = [(b, tuple(b.node.getPos()), b.radius * assist, STRETCH) for b in self.balloons if b.alive]
        hit, t = picking.closest_hit(tuple(origin), tuple(d), targets)
        if hit is None:
            return None, None
        return hit, origin + d * t

    def in_radius(self, center, radius):
        c = tuple(center)
        return [b for b in self.balloons if b.alive and picking.distance(tuple(b.node.getPos()), c) <= radius]
