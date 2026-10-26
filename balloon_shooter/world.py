"""The environment: sky dome, valley, mountains, clouds, scenery and the booth."""

import math
import random

from panda3d.core import CardMaker, ColorBlendAttrib, NodePath, TransparencyAttrib, Vec3, Vec4

from . import config as C
from . import geometry as G
from . import shaders


class World:
    def __init__(self, base, quality="high"):
        self.base = base
        self.root = base.render.attachNewNode("world")
        self.time = 0.0
        self.quality = quality

        self._lit = shaders.lit()
        self._sky_shader = shaders.sky()

        self.sky = self._build_sky()
        self.terrain = self._build_terrain()
        self.scenery = self._build_scenery()
        self.clouds = []
        self.cloud_root = self.root.attachNewNode("clouds")
        self.cloud_root.setTransparency(TransparencyAttrib.MAlpha)
        self.cloud_root.setDepthWrite(False)
        self.cloud_root.setBin("transparent", 0)
        self.cloud_root.setLightOff()
        self._build_clouds(22 if quality == "high" else 12)
        self.hot_air = self._build_hot_air_balloons()
        self.booth = self._build_booth()
        self.palette = None
        self.set_sky("day")

    # -- lighting -----------------------------------------------------------------
    def set_sky(self, name):
        p = C.SKIES[name]
        self.palette = p
        render = self.base.render
        sun = Vec3(*p["sun_dir"]).normalized()
        render.setShaderInput("u_sun_dir", sun)
        render.setShaderInput("u_sun_col", Vec3(*p["sun"]))
        render.setShaderInput("u_ambient", Vec3(*p["ambient"]))
        render.setShaderInput("u_horizon", Vec3(*p["horizon"]))
        render.setShaderInput("u_zenith", Vec3(*p["zenith"]))
        render.setShaderInput("u_stars", float(p["stars"]))
        render.setShaderInput("u_fog", 0.0013)
        render.setShaderInput("u_tint", Vec4(1, 1, 1, 1))
        render.setShaderInput("u_cam", Vec3(0, 0, 0))
        render.setShaderInput("u_time", 0.0)
        self.base.setBackgroundColor(*p["horizon"], 1)
        # clouds pick up the colour of the sun and fade into the horizon
        horizon = Vec3(*p["horizon"])
        sun_tint = Vec3(1, 1, 1) * 0.45 + Vec3(*p["sun"]) * 0.55
        for puff, lit, haze in self.puffs:
            c = sun_tint * lit * (1 - haze) + horizon * haze
            puff.setColorScale(c.x, c.y, c.z, 1.0)

    # -- builders -----------------------------------------------------------------
    def _build_sky(self):
        dome = G.ico_sphere(3, name="sky")
        dome.reparentTo(self.root)
        dome.setScale(1800)
        dome.setTwoSided(True)
        dome.setShader(self._sky_shader)
        dome.setBin("background", 0)
        dome.setDepthWrite(False)
        dome.setDepthTest(False)
        dome.setLightOff()
        dome.setCompass()      # sky follows the camera
        return dome

    def _build_terrain(self):
        cells = 110 if self.quality == "high" else 70
        terrain, self.noise = G.terrain_mesh(cells=cells)
        terrain.reparentTo(self.root)
        terrain.setShader(self._lit)
        return terrain

    def _build_scenery(self):
        root = self.root.attachNewNode("scenery")
        root.setShader(self._lit)
        rnd = random.Random(11)
        pine = NodePath("pine")
        trunk = G.cylinder(0.5, 2.5, 6, (0.40, 0.27, 0.18, 1))
        trunk.setP(90)
        trunk.reparentTo(pine)
        for i, (r, h, z) in enumerate(((3.2, 5.0, 2.0), (2.5, 4.4, 4.6), (1.7, 3.8, 7.0))):
            cone = G.cone_up(r, h, 7, (0.16, 0.42 + i * 0.04, 0.24, 1))
            cone.setZ(z)
            cone.reparentTo(pine)
        pine.flattenStrong()
        count = 0
        attempts = 0
        while count < (180 if self.quality == "high" else 90) and attempts < 2000:
            attempts += 1
            x = rnd.uniform(-420, 420)
            y = rnd.uniform(60, 480)
            h = G.terrain_height(self.noise, x, y)
            if not (-85 < h < -20):
                continue
            tree = pine.instanceTo(root)
            tree.setPos(x, y, h - 0.5)
            tree.setScale(rnd.uniform(1.2, 2.4))
            tree.setH(rnd.uniform(0, 360))
            count += 1
        # a little lake in the valley floor
        lake = G.MeshBuilder("lake")
        col = (0.22, 0.42, 0.62, 1)
        segs = 40
        center = lake.vertex((0, 0, 0), (0, 0, 1), col)
        ring = [lake.vertex((math.cos(a) * 60 * (1 + 0.15 * math.sin(a * 3)),
                             math.sin(a) * 34 * (1 + 0.1 * math.cos(a * 2)), 0), (0, 0, 1), col)
                for a in [2 * math.pi * s / segs for s in range(segs)]]
        for s in range(segs):
            lake.tri(center, ring[s], ring[(s + 1) % segs])
        lake_np = lake.node()
        lake_np.reparentTo(root)
        lake_np.setPos(-30, 120, G.terrain_height(self.noise, -30, 120) + 1.5)
        return root

    def _build_clouds(self, count):
        """Billboard clouds: clusters of soft puffs, lit from above, tinted by distance."""
        rnd = random.Random(5)
        textures = [G.cloud_puff_texture(128, seed) for seed in (1, 2, 3)]
        card = CardMaker("puff")
        card.setFrame(-1, 1, -1, 1)
        self.puffs = []
        for i in range(count):
            cloud = self.cloud_root.attachNewNode(f"cloud{i}")
            dist = rnd.uniform(220, 700)
            ang = rnd.uniform(-70, 70)
            x = math.sin(math.radians(ang)) * dist
            y = math.cos(math.radians(ang)) * dist
            z = rnd.uniform(25, 80) + dist * 0.07
            cloud.setPos(x, y, z)
            scale = rnd.uniform(1.4, 2.6)
            width = rnd.uniform(14, 26)
            haze = min(0.6, dist / 1100)
            for k in range(rnd.randint(7, 12)):
                p = cloud.attachNewNode(card.generate())
                p.setTexture(rnd.choice(textures))
                px = rnd.uniform(-width, width) * scale
                pz = rnd.uniform(-2, 6) * scale * (1 - abs(px) / (width * scale) * 0.6)
                p.setPos(px, rnd.uniform(-3, 3), pz)
                p.setScale(rnd.uniform(7, 12) * scale)
                p.setBillboardPointEye()
                # undersides are a touch darker, tops catch the sun
                lit = 0.97 + 0.13 * max(0.0, min(1.0, (pz / scale + 2) / 8))
                self.puffs.append((p, lit, haze))
            self.clouds.append([cloud, rnd.uniform(1.0, 3.0)])

    def _build_hot_air_balloons(self):
        """A few big balloons drifting far away, for scale and charm."""
        out = []
        rnd = random.Random(21)
        envelope = G.balloon_mesh(18, 14)
        colors = [(0.95, 0.35, 0.25, 1), (0.25, 0.55, 0.95, 1), (0.98, 0.78, 0.25, 1), (0.55, 0.85, 0.40, 1)]
        for i, col in enumerate(colors):
            hab = NodePath(f"hab{i}")
            env = envelope.copyTo(hab)
            env.setColor(*col)
            env.setScale(1.0, 1.0, 1.1)
            stripe = envelope.copyTo(hab)
            stripe.setColor(1, 1, 1, 1)
            stripe.setScale(1.01, 1.01, 0.35)
            stripe.setZ(0.15)
            basket = G.box(0.6, 0.6, 0.45, (0.55, 0.38, 0.22, 1))
            basket.reparentTo(hab)
            basket.setZ(-1.9)
            hab.reparentTo(self.root)
            hab.setShader(self._lit)
            hab.setScale(6 + rnd.random() * 3)
            ang = math.radians(-50 + i * 33 + rnd.uniform(-8, 8))
            dist = rnd.uniform(160, 320)
            hab.setPos(math.sin(ang) * dist, math.cos(ang) * dist, rnd.uniform(10, 50))
            out.append([hab, rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.4)])
        return out

    def _build_booth(self):
        """The carnival booth around the player: counter, striped poles and awning."""
        booth = self.base.render.attachNewNode("booth")
        booth.setShader(self._lit)
        wood = (0.72, 0.46, 0.27, 1)
        trim = (0.50, 0.30, 0.17, 1)
        red = (0.90, 0.16, 0.22, 1)
        cream = (0.99, 0.95, 0.88, 1)
        counter = G.box(12.0, 0.8, 0.18, wood)
        counter.reparentTo(booth)
        counter.setPos(0, 4.05, -1.68)
        lip = G.box(12.0, 0.12, 0.26, trim)
        lip.reparentTo(booth)
        lip.setPos(0, 4.47, -1.72)
        for i in range(-6, 7):
            panel = G.box(1.0, 0.1, 1.6, red if i % 2 else cream)
            panel.reparentTo(booth)
            panel.setPos(i * 1.0, 4.5, -2.65)
        for x in (-4.3, 4.3):
            pole = G.cylinder(0.11, 6.0, 12, cream)
            pole.setP(90)
            pole.reparentTo(booth)
            pole.setPos(x, 4.6, -2.0)
            for k in range(5):
                band = G.cylinder(0.118, 0.45, 12, red)
                band.setP(90)
                band.reparentTo(booth)
                band.setPos(x, 4.6, -1.6 + k * 0.9)
        # scalloped awning valance along the top of the view
        for i in range(-7, 8):
            col = red if i % 2 else cream
            strip = G.box(0.7, 0.06, 0.22, col)
            strip.reparentTo(booth)
            strip.setPos(i * 0.7, 4.6, 2.62)
            mb = G.MeshBuilder("scallop")
            segs = 8
            for k in range(segs):
                a0 = math.pi + math.pi * k / segs
                a1 = math.pi + math.pi * (k + 1) / segs
                mb.flat_tri((0, 0, 0), (math.cos(a1) * 0.35, 0, math.sin(a1) * 0.2),
                            (math.cos(a0) * 0.35, 0, math.sin(a0) * 0.2), col)
            sc = mb.node()
            sc.setTwoSided(True)
            sc.reparentTo(booth)
            sc.setPos(i * 0.7, 4.57, 2.51)
        booth.flattenStrong()
        return booth

    # -- per frame --------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        render = self.base.render
        render.setShaderInput("u_time", self.time)
        render.setShaderInput("u_cam", self.base.camera.getPos(render))
        for cloud, speed in self.clouds:
            cloud.setX(cloud.getX() + speed * dt)
            if cloud.getX() > 520:
                cloud.setX(-520)
        for hab, phase, speed in self.hot_air:
            hab.setX(hab.getX() + speed * dt * 0.8)
            hab.setZ(hab.getZ() + math.sin(self.time * 0.3 + phase) * dt * 0.6)
            if hab.getX() > 380:
                hab.setX(-380)


def additive(np_):
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                        ColorBlendAttrib.OOne))
    np_.setDepthWrite(False)
    np_.setTransparency(TransparencyAttrib.MNone)
    np_.setBin("fixed", 10)
    return np_
