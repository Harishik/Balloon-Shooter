"""Ray tests used for shooting. Plain tuples so they are engine independent."""

import math


def ray_ellipsoid(origin, direction, center, radius, stretch=1.0):
    """Distance along a normalised ray to an ellipsoid, or None on a miss.

    The ellipsoid has ``radius`` across X/Y and ``radius * stretch`` along Z,
    which matches the balloon's slightly tall shape.
    """
    sz = 1.0 / stretch
    ox, oy, oz = (origin[0] - center[0], origin[1] - center[1], (origin[2] - center[2]) * sz)
    dx, dy, dz = direction[0], direction[1], direction[2] * sz
    a = dx * dx + dy * dy + dz * dz
    b = 2.0 * (ox * dx + oy * dy + oz * dz)
    c = ox * ox + oy * oy + oz * oz - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0 or a == 0:
        return None
    root = math.sqrt(disc)
    t = (-b - root) / (2 * a)
    if t < 0:
        t = (-b + root) / (2 * a)
    return t if t >= 0 else None


def closest_hit(origin, direction, targets):
    """``targets`` is an iterable of (obj, center, radius, stretch).

    Returns (obj, distance) for the nearest hit or (None, None).
    """
    best, best_t = None, None
    for obj, center, radius, stretch in targets:
        t = ray_ellipsoid(origin, direction, center, radius, stretch)
        if t is not None and (best_t is None or t < best_t):
            best, best_t = obj, t
    return best, best_t


def distance(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
