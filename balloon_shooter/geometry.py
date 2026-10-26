"""Procedural meshes and textures. Everything in the world is generated here,
so the game ships without any model files."""

import math
import random

import numpy as np
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    PNMImage,
    Texture,
    Vec3,
)


class MeshBuilder:
    """Collects vertices (position, normal, colour) and triangles."""

    def __init__(self, name):
        self.name = name
        self.verts = []
        self.tris = []

    def vertex(self, pos, normal, color=(1, 1, 1, 1)):
        self.verts.append((pos, normal, color))
        return len(self.verts) - 1

    def tri(self, a, b, c):
        self.tris.append((a, b, c))

    def flat_tri(self, p0, p1, p2, color):
        """Add a triangle with its own face normal (faceted, low-poly look)."""
        n = (Vec3(*p1) - Vec3(*p0)).cross(Vec3(*p2) - Vec3(*p0))
        if n.length() == 0:
            return
        n.normalize()
        a = self.vertex(p0, n, color)
        b = self.vertex(p1, n, color)
        c = self.vertex(p2, n, color)
        self.tri(a, b, c)

    def node(self):
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(self.name, fmt, Geom.UHStatic)
        vdata.setNumRows(len(self.verts))
        vw, nw, cw = (GeomVertexWriter(vdata, c) for c in ("vertex", "normal", "color"))
        for pos, normal, color in self.verts:
            vw.addData3(*pos)
            nw.addData3(*normal)
            cw.addData4(*color)
        prim = GeomTriangles(Geom.UHStatic)
        for a, b, c in self.tris:
            prim.addVertices(a, b, c)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        gn = GeomNode(self.name)
        gn.addGeom(geom)
        return NodePath(gn)


def _lathe(mb, profile, segments, color=(1, 1, 1, 1)):
    """Revolve a list of (radius, z) points around the Z axis with smooth normals."""
    rows = []
    for i, (r, z) in enumerate(profile):
        # tangent along the profile gives the normal
        r0, z0 = profile[max(0, i - 1)]
        r1, z1 = profile[min(len(profile) - 1, i + 1)]
        tr, tz = r1 - r0, z1 - z0
        nr, nz = -tz, tr
        ln = math.hypot(nr, nz) or 1.0
        nr, nz = nr / ln, nz / ln
        row = []
        for s in range(segments + 1):
            a = 2 * math.pi * s / segments
            ca, sa = math.cos(a), math.sin(a)
            row.append(mb.vertex((r * ca, r * sa, z), (nr * ca, nr * sa, nz), color))
        rows.append(row)
    for i in range(len(rows) - 1):
        for s in range(segments):
            a, b = rows[i][s], rows[i][s + 1]
            c, d = rows[i + 1][s], rows[i + 1][s + 1]
            mb.tri(a, c, b)
            mb.tri(b, c, d)


def balloon_mesh(segments=28, rings=22):
    """A classic party balloon: round top, tapered bottom and a little knot.
    Unit radius, about 2.4 units tall, centred near the widest point."""
    mb = MeshBuilder("balloon")
    profile = []
    for i in range(rings + 1):
        th = math.pi * i / rings          # 0 = top, pi = bottom
        z = math.cos(th) * 1.15
        taper = 1.0 - 0.42 * (th / math.pi) ** 3
        r = math.sin(th) * taper
        if i == rings:
            r = 0.0
        profile.append((max(r, 0.0), z))
    profile[-1] = (0.0, -1.18)
    _lathe(mb, profile, segments)
    knot = [(0.0, -1.10), (0.10, -1.16), (0.14, -1.24), (0.09, -1.30), (0.0, -1.31)]
    _lathe(mb, knot, 10)
    return mb.node()


def string_mesh(length=2.6, segments=10, width=0.025):
    """A gently curved string hanging below the knot, as a thin triangular tube."""
    mb = MeshBuilder("string")
    color = (0.92, 0.92, 0.95, 1)
    sides = 3
    rows = []
    for i in range(segments + 1):
        t = i / segments
        x = math.sin(t * math.pi * 1.3) * 0.18 * t
        z = -1.30 - t * length
        row = []
        for s in range(sides):
            a = 2 * math.pi * s / sides
            n = (math.cos(a), math.sin(a), 0)
            row.append(mb.vertex((x + n[0] * width, n[1] * width, z), n, color))
        rows.append(row)
    for i in range(segments):
        for s in range(sides):
            a, b = rows[i][s], rows[i][(s + 1) % sides]
            c, d = rows[i + 1][s], rows[i + 1][(s + 1) % sides]
            mb.tri(a, c, b)
            mb.tri(b, c, d)
    return mb.node()


def ico_sphere(subdiv=2, color=(1, 1, 1, 1), flat=False, name="sphere"):
    t = (1 + 5 ** 0.5) / 2
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
             (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [Vec3(*v).normalized() for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
             (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
             (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                verts.append(((verts[a] + verts[b]) * 0.5).normalized())
                cache[key] = len(verts) - 1
            return cache[key]

        new = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new
    mb = MeshBuilder(name)
    if flat:
        for a, b, c in faces:
            mb.flat_tri(tuple(verts[a]), tuple(verts[b]), tuple(verts[c]), color)
    else:
        idx = [mb.vertex(tuple(v), tuple(v), color) for v in verts]
        for a, b, c in faces:
            mb.tri(idx[a], idx[b], idx[c])
    return mb.node()


def box(sx, sy, sz, color, name="box"):
    mb = MeshBuilder(name)
    x, y, z = sx / 2, sy / 2, sz / 2
    corners = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
               (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    quads = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0)]
    for a, b, c, d in quads:
        mb.flat_tri(corners[a], corners[b], corners[c], color)
        mb.flat_tri(corners[a], corners[c], corners[d], color)
    return mb.node()


def cylinder(radius, height, segments=12, color=(1, 1, 1, 1), radius_top=None, name="cyl", caps=True):
    """Along +Y (handy for barrels). Set radius_top=0 for a cone."""
    mb = MeshBuilder(name)
    rt = radius if radius_top is None else radius_top
    for s in range(segments):
        a0 = 2 * math.pi * s / segments
        a1 = 2 * math.pi * (s + 1) / segments
        p = lambda a, r, y: (math.cos(a) * r, y, math.sin(a) * r)
        b0, b1 = p(a0, radius, 0), p(a1, radius, 0)
        t0, t1 = p(a0, rt, height), p(a1, rt, height)
        mb.flat_tri(b0, t0, b1, color)
        if rt > 0:
            mb.flat_tri(b1, t0, t1, color)
        if caps:
            mb.flat_tri((0, 0, 0), b0, b1, color)
            if rt > 0:
                mb.flat_tri((0, height, 0), t1, t0, color)
    return mb.node()


def cone_up(radius, height, segments=8, color=(1, 1, 1, 1)):
    """A cone pointing up +Z (trees)."""
    np_ = cylinder(radius, height, segments, color, radius_top=0.0, name="cone")
    np_.setP(90)
    holder = NodePath("cone")
    np_.reparentTo(holder)
    np_.flattenStrong()
    return holder


# --- terrain -------------------------------------------------------------------
class ValueNoise:
    def __init__(self, seed=3):
        r = random.Random(seed)
        self.perm = list(range(256))
        r.shuffle(self.perm)
        self.perm += self.perm
        self.vals = [r.random() for _ in range(256)]

    def _v(self, ix, iy):
        return self.vals[self.perm[(self.perm[ix & 255] + iy) & 255]]

    def __call__(self, x, y):
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x - ix, y - iy
        ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = self._v(ix, iy), self._v(ix + 1, iy)
        c, d = self._v(ix, iy + 1), self._v(ix + 1, iy + 1)
        return (a + (b - a) * ux) + ((c + (d - c) * ux) - (a + (b - a) * ux)) * uy

    def fbm(self, x, y, octaves=4):
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += self(x * freq, y * freq) * amp
            norm += amp
            amp *= 0.5
            freq *= 2.03
        return total / norm


def terrain_height(noise, x, y):
    """A valley below the player that rises into a ring of mountains."""
    d = math.hypot(x, y * 0.85)
    base = -85.0
    hills = noise.fbm(x * 0.010, y * 0.010) * 34.0
    ridge = max(0.0, (d - 420.0) / 320.0) ** 1.5 * 150.0
    peaks = noise.fbm(x * 0.005 + 40, y * 0.005 + 11, 5) ** 2 * 150.0 * min(1.0, max(0.0, (d - 460) / 260))
    return base + hills + ridge + peaks


def terrain_color(h, slope, rnd):
    if h > 40:
        c = (0.95, 0.96, 1.0)                          # snow
    elif h > 0 or slope < 0.6:
        c = (0.50, 0.48, 0.55)                         # rock
    elif h > -45:
        c = (0.30, 0.54, 0.30)                         # high grass
    else:
        c = (0.40, 0.66, 0.33)                         # meadow
    j = 0.95 + rnd.random() * 0.10
    return (c[0] * j, c[1] * j, c[2] * j, 1)


def terrain_mesh(size=1800.0, cells=110, seed=3):
    noise = ValueNoise(seed)
    rnd = random.Random(seed)
    step = size / cells
    half = size / 2
    heights = [[terrain_height(noise, -half + i * step, -half + j * step + 160) for j in range(cells + 1)]
               for i in range(cells + 1)]
    mb = MeshBuilder("terrain")
    for i in range(cells):
        for j in range(cells):
            x0, x1 = -half + i * step, -half + (i + 1) * step
            y0, y1 = -half + j * step + 160, -half + (j + 1) * step + 160
            p00 = (x0, y0, heights[i][j])
            p10 = (x1, y0, heights[i + 1][j])
            p01 = (x0, y1, heights[i][j + 1])
            p11 = (x1, y1, heights[i + 1][j + 1])
            for a, b, c in ((p00, p10, p11), (p00, p11, p01)):
                n = (Vec3(*b) - Vec3(*a)).cross(Vec3(*c) - Vec3(*a)).normalized()
                h = (a[2] + b[2] + c[2]) / 3
                mb.flat_tri(a, b, c, terrain_color(h, n.z, rnd))
    return mb.node(), noise


# --- textures --------------------------------------------------------------------
def _texture(img, name):
    tex = Texture(name)
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def soft_dot_texture(size=64):
    img = PNMImage(size, size, 4)
    c = (size - 1) / 2
    for x in range(size):
        for y in range(size):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1.0 - d) ** 2
            img.setXelA(x, y, 1, 1, 1, a)
    return _texture(img, "soft_dot")


def ring_texture(size=128, thickness=0.12):
    img = PNMImage(size, size, 4)
    c = (size - 1) / 2
    for x in range(size):
        for y in range(size):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1.0 - abs(d - (1 - thickness)) / thickness)
            img.setXelA(x, y, 1, 1, 1, a ** 1.5)
    return _texture(img, "ring")


def star_texture(size=64):
    img = PNMImage(size, size, 4)
    c = (size - 1) / 2
    for x in range(size):
        for y in range(size):
            dx, dy = (x - c) / c, (y - c) / c
            d = math.hypot(dx, dy)
            horiz = max(0.0, 1 - abs(dy) * 8) * max(0.0, 1 - abs(dx))
            vert = max(0.0, 1 - abs(dx) * 8) * max(0.0, 1 - abs(dy))
            spikes = horiz + vert
            a = min(1.0, spikes + max(0.0, 1 - d * 2.2) ** 2)
            img.setXelA(x, y, 1, 1, 1, a)
    return _texture(img, "star")


def vignette_texture(size=256):
    img = PNMImage(size, size, 4)
    c = (size - 1) / 2
    for x in range(size):
        for y in range(size):
            d = math.hypot(x - c, y - c) / c
            a = min(1.0, max(0.0, d - 0.55) / 0.75) ** 1.8
            img.setXelA(x, y, 0, 0, 0.05, a)
    return _texture(img, "vignette")


def rounded_rect_texture(w, h, radius, fill, border=None, border_w=0, name="rrect"):
    """A rounded rectangle with optional border, for UI panels and buttons.
    ``fill`` may be a single RGBA colour or (top, bottom) for a vertical gradient."""
    single = len(fill) == 4 and not isinstance(fill[0], (tuple, list))
    top, bottom = (fill, fill) if single else fill
    top, bottom = np.array(top, dtype=np.float32), np.array(bottom, dtype=np.float32)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    t = (ys / max(1, h - 1))[..., None]
    col = top + (bottom - top) * t
    qx = np.maximum(np.abs(xs + 0.5 - w / 2) - (w / 2 - radius), 0.0)
    qy = np.maximum(np.abs(ys + 0.5 - h / 2) - (h / 2 - radius), 0.0)
    d = np.hypot(qx, qy) - radius
    alpha = np.clip(0.5 - d, 0.0, 1.0)
    if border is not None and border_w:
        k = np.clip(d + border_w + 0.5, 0.0, 1.0)[..., None]
        col = col + (np.array(border, dtype=np.float32) - col) * k
    col[..., 3] *= alpha
    return _texture_from_array(col, name)


def _texture_from_array(rgba, name):
    """Build a texture from an (h, w, 4) float array, row 0 at the top."""
    h, w = rgba.shape[:2]
    data = (np.clip(rgba[::-1], 0, 1) * 255).astype(np.uint8)
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.TUnsignedByte, Texture.FRgba8)
    tex.setRamImageAs(data.tobytes(), "RGBA")
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def cloud_puff_texture(size=128, seed=1):
    """A soft, lumpy white puff (alpha) used for billboard clouds."""
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    d = np.hypot(xs - c, ys - c) / c
    # cheap value noise: upsampled random grids at a few octaves
    noise = np.zeros((size, size), np.float32)
    amp = 1.0
    for cells in (4, 8, 16):
        grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
        gx = xs / (size - 1) * cells
        gy = ys / (size - 1) * cells
        x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
        x1, y1 = np.minimum(x0 + 1, cells), np.minimum(y0 + 1, cells)
        fx, fy = gx - x0, gy - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
        bot = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
        noise += (top * (1 - fy) + bot * fy) * amp
        amp *= 0.5
    noise /= 1.75
    alpha = np.clip((1.0 - d) * 1.6 - (1 - noise) * 0.9, 0, 1) ** 1.3
    shade = 0.82 + 0.18 * (1 - ys / (size - 1))     # brighter on top
    rgba = np.zeros((size, size, 4), np.float32)
    rgba[..., 0] = shade
    rgba[..., 1] = shade
    rgba[..., 2] = shade * 1.02
    rgba[..., 3] = alpha
    return _texture_from_array(rgba, f"puff{seed}")
