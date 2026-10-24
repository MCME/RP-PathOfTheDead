"""Paints the spider webs' starting textures: Shelob's silk - thick grey
cords, a thin film between some, slime beading on them - procedurally, 32
texels a block, as RP-Mordor's webs are.

They're a start, meant to be painted over: run it once, then edit the PNGs by
hand. It never overwrites a texture that exists unless told to (--force), and
build.py, which encodes them for the shaders, runs on whatever is there.

    python .tools/spiderwebs/paint.py [--force] [names...]
"""

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PACK = Path(__file__).resolve().parents[2]
BLOCK = PACK / "assets/minecraft/textures/block"
MORDOR = PACK.parent / "RP-Mordor/assets/minecraft/textures/block"
PX = 32   # texels a block

SILK = np.array([214, 211, 198], float)
SILK_DARK = np.array([150, 148, 136], float)
SLIME = np.array([186, 194, 132], float)
SLIME_LIGHT = np.array([236, 238, 204], float)
HUSK = np.array([92, 84, 70], float)


class Canvas:
    """Premultiplied-free RGBA in floats, painted over: each stroke lies
    over what's there."""

    def __init__(self, w, h, seed):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3))
        self.a = np.zeros((h, w))
        self.rng = random.Random(seed)

    def plot(self, x, y, color, alpha):
        x, y = int(round(x)), int(round(y))
        if not (0 <= x < self.w and 0 <= y < self.h) or alpha <= 0:
            return
        under = self.a[y, x]
        out = alpha + under * (1.0 - alpha)
        self.rgb[y, x] = (color * alpha + self.rgb[y, x] * under * (1.0 - alpha)) / out
        self.a[y, x] = out

    def cord(self, pts, width=1, alpha=0.85, shade=1.0, step=0.35):
        """A silk cord through pts, its brightness wandering along it."""
        seen = set()
        phase = self.rng.random() * 10.0
        length = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(d / step))
            for i in range(n + 1):
                t = i / n
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                s = length + d * t
                for k in range(width):
                    key = (int(round(x + (k if abs(x1 - x0) < abs(y1 - y0) else 0))),
                           int(round(y + (0 if abs(x1 - x0) < abs(y1 - y0) else k))))
                    if key in seen:
                        continue
                    seen.add(key)
                    v = 0.82 + 0.18 * math.sin(s * 0.45 + phase) + 0.08 * self.rng.random()
                    color = SILK * v * shade if k == 0 else SILK_DARK * v * shade
                    self.plot(key[0], key[1], np.clip(color, 0, 255), alpha * (0.85 + 0.15 * self.rng.random()))
            length += d

    def bead(self, x, y, r=1):
        """A bead of slime caught on a cord, its top lit."""
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r + 0.5:
                    self.plot(x + dx, y + dy, SLIME, 0.92)
        self.plot(x - (r > 0), y - (r > 0), SLIME_LIGHT, 0.95)

    def film(self, poly, alpha=0.18):
        """The thin film of silk spun between cords."""
        layer = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(layer).polygon([(float(x), float(y)) for x, y in poly], fill=255)
        mask = np.asarray(layer, float) / 255.0
        noise = np.array([[self.rng.random() for _ in range(self.w)] for _ in range(self.h)])
        a = mask * alpha * (0.6 + 0.6 * noise)
        under = self.a
        out = a + under * (1.0 - a)
        safe = np.maximum(out, 1e-6)
        self.rgb = (SILK[None, None] * 0.92 * a[..., None] + self.rgb * (under * (1.0 - a))[..., None]) / safe[..., None]
        self.a = out

    def tear(self, cx, cy, r):
        """A hole torn through, its edge's cords left dangling."""
        for y in range(self.h):
            for x in range(self.w):
                if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                    self.a[y, x] = 0.0
        for _ in range(self.rng.randint(2, 4)):
            a = self.rng.uniform(math.pi * 1.1, math.pi * 1.9)
            x, y = cx + math.cos(a) * r, cy - math.sin(a) * r * 0.2 - r * 0.6
            self.cord(sag_line((x, y), (x + self.rng.uniform(-2, 2), y + self.rng.uniform(3, r)), 0.5), alpha=0.75)

    def image(self):
        out = np.zeros((self.h, self.w, 4), np.uint8)
        out[..., :3] = np.clip(self.rgb, 0, 255).astype(np.uint8)
        out[..., 3] = np.clip(self.a * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(out, "RGBA")


def sag_line(p0, p1, sag, n=24):
    """From p0 to p1, sagging by sag texels at its middle."""
    return [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + sag * 4.0 * t * (1.0 - t))
            for t in (i / n for i in range(n + 1))]


def hanging(c, x, top, bottom, sway=1.2):
    """A cord hanging from top to bottom at about x, wavering."""
    f, ph = c.rng.uniform(0.08, 0.2), c.rng.random() * 6.3
    return [(x + sway * math.sin(y * f + ph) * (y - top) / max(bottom - top, 1), y)
            for y in np.linspace(top, bottom, max(2, int(bottom - top) + 1))]


def tip(c, x, y):
    """How a hanging cord ends: a glob, a fray, or nothing."""
    k = c.rng.random()
    if k < 0.45:
        c.bead(x, y, 1)
        if c.rng.random() < 0.5:
            c.plot(x, y + 2, SLIME, 0.7)     # the drop about to fall
    elif k < 0.75:
        c.cord([(x, y), (x - 1.5, y + 3)], alpha=0.6)
        c.cord([(x, y), (x + 1.5, y + 2.5)], alpha=0.6)


def beads_along(c, pts, share):
    for x, y in pts[2::3]:
        if c.rng.random() < share:
            c.bead(x, y, 0 if c.rng.random() < 0.6 else 1)


# ------------------------------------------------------------------ the kinds

def drops(c, n, reach=(0.55, 1.0), main=True, start=0, slime=0.12, thick=0.25):
    """Cords hanging from the top. With main, one down the middle to the bottom,
    for an extension below to go on from."""
    if main:
        pts = hanging(c, c.w / 2 - 0.5, start, c.h - 1, sway=0.6)
        c.cord(pts, width=2, alpha=0.92)
        beads_along(c, pts, slime)
    for _ in range(n):
        x = c.w / 2 + c.rng.uniform(-0.38, 0.38) * c.w
        bottom = c.h * c.rng.uniform(*reach) - 1
        pts = hanging(c, x, start, bottom)
        c.cord(pts, width=2 if c.rng.random() < thick else 1, alpha=c.rng.uniform(0.7, 0.92))
        beads_along(c, pts, slime)
        tip(c, pts[-1][0], pts[-1][1])
        if c.rng.random() < 0.4:   # bridged to the middle cord near the top
            y = c.rng.uniform(1, c.h * 0.3)
            c.cord(sag_line((x, y), (c.w / 2, y + c.rng.uniform(-2, 2)), 1.5), alpha=0.7)


def sag(c, cords=3, drips=4):
    """Cords slung between the top corners, sagging, drips hanging off them."""
    lowest = None
    for i in range(cords):
        depth = c.h * (0.25 + 0.55 * (i + c.rng.random()) / cords)
        pts = sag_line((0, c.rng.uniform(0, 2)), (c.w - 1, c.rng.uniform(0, 2)), depth, n=48)
        c.cord(pts, width=2 if i == cords - 1 else 1, alpha=0.9)
        beads_along(c, pts, 0.1)
        lowest = pts
    for _ in range(drips):
        x, y = lowest[c.rng.randint(8, len(lowest) - 9)]
        pts = hanging(c, x, y, min(c.h - 2, y + c.rng.uniform(3, 10)), sway=0.4)
        c.cord(pts, alpha=0.8)
        tip(c, pts[-1][0], pts[-1][1])


def guy(c):
    """A taut line from the top left down to the bottom right, splayed where
    it's fixed at either end."""
    pts = sag_line((1, 0), (c.w - 2, c.h - 1), 3, n=64)
    c.cord(pts, width=2, alpha=0.95)
    c.cord([(x + 2, y + 1) for x, y in pts[4:-6]], alpha=0.6)
    beads_along(c, pts, 0.12)
    for _ in range(3):
        a = pts[c.rng.randint(4, 16)]
        c.cord(sag_line(a, (c.rng.uniform(0, c.w * 0.5), 0), -1), alpha=0.75)
        b = pts[c.rng.randint(-16, -5)]
        c.cord(sag_line(b, (c.w - 1, c.rng.uniform(c.h * 0.6, c.h - 1)), 1), alpha=0.75)


def net(c, density=1.0, reach=(0.6, 1.0), tears=0, frayed=False, film=0.6):
    """Shelob's sheet: a cord along the top, cords hanging from it, cross
    threads sagging between them, a film spun over some of it."""
    top = sag_line((0, c.rng.uniform(0, 1.5)), (c.w - 1, c.rng.uniform(0, 1.5)), c.rng.uniform(1, 3), n=48)
    c.cord(top, width=2, alpha=0.95)
    n = max(3, int(c.w / 7 * density))
    lines = []
    for i in range(n):
        x = (i + 0.5 + c.rng.uniform(-0.35, 0.35)) * c.w / n
        bottom = c.h * c.rng.uniform(*(reach if not frayed else (reach[0] * 0.8, reach[1]))) - 1
        pts = hanging(c, x, 1, bottom, sway=2.5)
        lines.append(pts)
        c.cord(pts, width=2 if c.rng.random() < 0.3 else 1, alpha=c.rng.uniform(0.75, 0.95))
        beads_along(c, pts, 0.08)
        tip(c, pts[-1][0], pts[-1][1])
    rungs = []
    for _ in range(int(c.w * c.h / 90 * density)):
        i = c.rng.randrange(len(lines) - 1)
        a, b = lines[i], lines[i + 1 + (c.rng.random() < 0.25 and i + 2 < len(lines))]
        ya = c.rng.uniform(0.05, 0.95) * (len(a) - 1)
        yb = min(len(b) - 1, max(0, ya + c.rng.uniform(-6, 6)))
        p, q = a[int(ya)], b[int(yb)]
        pts = sag_line(p, q, c.rng.uniform(0.5, 3))
        c.cord(pts, alpha=c.rng.uniform(0.55, 0.85))
        rungs.append((p, q))
    for _ in range(int(len(rungs) * film * 0.35)):
        (p, q), (r, s) = c.rng.sample(rungs, 2)
        if abs(p[0] - r[0]) < c.w / n * 1.6 and abs(p[1] - r[1]) < 14:
            c.film([p, q, s, r], alpha=c.rng.uniform(0.1, 0.22))
    for _ in range(tears):
        c.tear(c.rng.uniform(0.2, 0.8) * c.w, c.rng.uniform(0.35, 0.8) * c.h, c.rng.uniform(3, 7))


def fan(c, film=0.5):
    """A corner web: cords out from the top right corner, threads sagging
    across them in rings, a film where they're close."""
    corner = (c.w - 1, 0)
    r = min(c.w, c.h)
    n = c.rng.randint(6, 9)
    spokes = []
    for i in range(n):
        a = (i + c.rng.uniform(-0.3, 0.3)) / (n - 1) * math.pi / 2
        length = r * c.rng.uniform(0.75, 1.15)
        end = (corner[0] - math.cos(a) * length, corner[1] + math.sin(a) * length)
        pts = sag_line(corner, end, c.rng.uniform(-1, 1.5))
        c.cord(pts, width=2 if i in (0, n - 1) else 1, alpha=0.9)
        spokes.append(pts)
    rings = sorted(c.rng.uniform(0.15, 0.95) for _ in range(c.rng.randint(4, 7)))
    for k, f in enumerate(rings):
        for i in range(n - 1):
            if c.rng.random() < 0.15:
                continue   # broken
            a, b = spokes[i], spokes[i + 1]
            p = a[min(len(a) - 1, int(f * len(a)))]
            q = b[min(len(b) - 1, int((f + c.rng.uniform(-0.05, 0.05)) * len(b)))]
            pts = sag_line(p, q, 1 + f * 2)
            c.cord(pts, alpha=0.75)
            beads_along(c, pts, 0.05)
            if k < 2 and c.rng.random() < film:
                c.film([corner, p, q], alpha=0.16)
    for _ in range(c.rng.randint(1, 3)):   # threads come loose at the rim
        s = spokes[c.rng.randrange(n)]
        x, y = s[-1]
        pts = hanging(c, x, y, min(c.h - 1, y + c.rng.uniform(3, 8)), 0.5)
        c.cord(pts, alpha=0.7)
        tip(c, pts[-1][0], pts[-1][1])


def span(c, density=1.0):
    """Between two walls: cords slung from the left edge to the right at
    every height, others hanging down between."""
    for i in range(int(c.h / 7 * density)):
        y = (i + c.rng.random()) * 7
        pts = sag_line((0, y), (c.w - 1, y + c.rng.uniform(-3, 3)), c.rng.uniform(1, 5), n=32)
        c.cord(pts, width=2 if c.rng.random() < 0.25 else 1, alpha=0.85)
        beads_along(c, pts, 0.07)
    drops(c, int(c.w / 8), reach=(0.4, 0.9), main=False, slime=0.05, thick=0.1)
    for _ in range(3):
        y = c.rng.uniform(0, c.h * 0.6)
        c.film([(0, y), (c.w - 1, y + 2), (c.w - 1, y + 9), (0, y + 7)], alpha=0.13)


def mesh(c, ragged=True, debris=0.0, film=0.5, scale=1.0):
    """A flat tangle, as a mat on the floor or silk plastered on a wall: short
    cords every which way, film over much of it, ragged at its rim."""
    cx, cy = c.w / 2, c.h / 2
    for _ in range(int(c.w * c.h / 26 * scale)):
        a = c.rng.random() * math.tau
        r = c.rng.random() ** 0.6 * c.w * 0.45
        p = (cx + math.cos(a) * r, cy + math.sin(a) * r)
        b = a + c.rng.uniform(-1.4, 1.4)
        length = c.rng.uniform(4, 14)
        q = (p[0] + math.cos(b) * length, p[1] + math.sin(b) * length)
        c.cord(sag_line(p, q, c.rng.uniform(-1.5, 1.5), n=12), alpha=c.rng.uniform(0.5, 0.85))
    for _ in range(int(8 * film)):
        a = c.rng.random() * math.tau
        r = c.rng.random() * c.w * 0.32
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        s = c.rng.uniform(3, 8)
        c.film([(x - s, y), (x, y - s * 0.8), (x + s, y + 1), (x, y + s * 0.9)], alpha=c.rng.uniform(0.12, 0.25))
    for _ in range(int(c.w * c.h / 120 * debris)):
        x, y = cx + c.rng.uniform(-0.35, 0.35) * c.w, cy + c.rng.uniform(-0.35, 0.35) * c.h
        c.plot(x, y, HUSK * c.rng.uniform(0.8, 1.2), 0.9)
        if c.rng.random() < 0.5:
            c.plot(x + 1, y, HUSK * 0.8, 0.85)
    for _ in range(int(c.w * c.h / 300)):
        c.bead(cx + c.rng.uniform(-0.3, 0.3) * c.w, cy + c.rng.uniform(-0.3, 0.3) * c.h, 1)
    if ragged:
        ys, xs = np.mgrid[0:c.h, 0:c.w]
        ang = np.arctan2(ys - cy, xs - cx)
        rim = 0.36 + 0.07 * np.sin(ang * 3 + c.rng.random() * 6) + 0.05 * np.sin(ang * 7 + c.rng.random() * 6)
        d = np.hypot((xs - cx) / c.w, (ys - cy) / c.h)
        c.a *= np.clip((rim - d) / 0.06, 0.0, 1.0)


def canopy(c):
    """A sheet slung flat under a ceiling: a lattice of cords, jittered, film
    across much of it, holes worn through."""
    step = 9
    pts = {}
    for j in range(c.h // step + 2):
        for i in range(c.w // step + 2):
            pts[i, j] = (i * step + c.rng.uniform(-3, 3), j * step + c.rng.uniform(-3, 3))
    for (i, j), p in pts.items():
        for di, dj in ((1, 0), (0, 1), (1, 1)):
            q = pts.get((i + di, j + dj))
            if q and c.rng.random() < (0.85 if di + dj == 1 else 0.35):
                c.cord(sag_line(p, q, c.rng.uniform(-1, 1), n=10), alpha=c.rng.uniform(0.6, 0.9))
                if c.rng.random() < 0.3:
                    r = pts.get((i, j + 1))
                    if r:
                        c.film([p, q, r], alpha=0.15)
    for _ in range(3):
        c.tear(c.rng.uniform(0.2, 0.8) * c.w, c.rng.uniform(0.2, 0.8) * c.h, c.rng.uniform(3, 6))
    ys, xs = np.mgrid[0:c.h, 0:c.w]
    edge = np.minimum.reduce([xs, ys, c.w - 1 - xs, c.h - 1 - ys]).astype(float)
    c.a *= np.clip(edge / 3.0, 0.0, 1.0) * 0.5 + 0.5


def wrapped(c, base, alpha, streaks=SLIME):
    """Silk wound round and round: a cocoon's skin, an egg sac's."""
    c.rgb[:] = base
    c.a[:] = alpha
    for _ in range(70):
        y = c.rng.uniform(-c.h, c.h)
        slope = c.rng.uniform(0.25, 0.7) * (1 if c.rng.random() < 0.5 else -1)
        pts = [(x, y + x * slope) for x in np.linspace(0, c.w - 1, 24)]
        c.cord(pts, alpha=0.55, shade=c.rng.uniform(0.85, 1.12))
    for _ in range(5):
        x = c.rng.uniform(0, c.w)
        pts = hanging(c, x, c.rng.uniform(0, c.h * 0.5), c.h - 1, 1.0)
        for px, py in pts:
            c.plot(px, py, streaks, 0.45)


def pool(c):
    """A pool of slime: its outline only - the shaders draw the slime."""
    ys, xs = np.mgrid[0:c.h, 0:c.w]
    cx, cy = c.w / 2, c.h / 2
    ang = np.arctan2(ys - cy, xs - cx)
    rim = 0.33 + 0.07 * np.sin(ang * 2 + c.rng.random() * 6) + 0.05 * np.sin(ang * 5 + c.rng.random() * 6)
    d = np.hypot((xs - cx) / c.w, (ys - cy) / c.h)
    c.rgb[:] = SLIME * 0.78
    c.a[:] = np.clip((rim - d) / 0.03, 0.0, 1.0) * 0.86
    for _ in range(6):   # smaller splashes round it
        a, r = c.rng.random() * math.tau, c.rng.uniform(0.36, 0.44)
        sx, sy = cx + math.cos(a) * r * c.w, cy + math.sin(a) * r * c.h
        s = c.rng.uniform(1.5, 3)
        c.a = np.maximum(c.a, np.clip((s - np.hypot(xs - sx, ys - sy)) / 1.0, 0, 1) * 0.8)


# ---------------------------------------------------------------- the textures

def strand(n, **kw):
    return lambda c: drops(c, n, **kw)


TEXTURES = {
    # strands (weeping_vines)
    "drop_1_a": (1, 1, strand(2)), "drop_1_b": (1, 1, strand(3)), "drop_1_c": (1, 1, strand(1, thick=1.0)),
    "drop_2_a": (1, 2, strand(2)), "drop_2_b": (1, 2, strand(4, reach=(0.3, 0.9))), "drop_2_c": (1, 2, strand(2, slime=0.3)),
    "extension_a": (1, 1, strand(2, reach=(0.4, 0.9))), "extension_b": (1, 1, strand(1, reach=(0.6, 1.0), slime=0.3)),
    "tangle_a": (1, 2, strand(7, reach=(0.25, 1.0), thick=0.15)), "tangle_b": (1, 2, strand(6, reach=(0.3, 0.8), slime=0.2)),
    "slime_strand_a": (1, 2, strand(2, slime=0.6, thick=0.8)), "slime_strand_b": (1, 2, strand(3, slime=0.5, thick=0.6)),
    "sag_2_a": (2, 1.5, lambda c: sag(c, 3, 4)), "sag_2_b": (2, 1.5, lambda c: sag(c, 2, 6)),
    "sag_3_a": (3, 2, lambda c: sag(c, 4, 6)), "sag_3_b": (3, 2, lambda c: sag(c, 3, 8)),
    "sag_diagonal_a": (2, 1, lambda c: sag(c, 3, 4)),
    "guy_a": (1.5, 2, guy), "guy_b": (1.5, 2, guy),
    "torn_a": (1, 1, strand(4, reach=(0.2, 0.7), main=False)), "torn_b": (1, 1, strand(3, reach=(0.3, 0.9), main=False, slime=0.3)),
    # sheets (twisting_vines)
    "sheet_1x1_a": (1, 1, lambda c: net(c, 1.2)), "sheet_1x1_b": (1, 1, lambda c: net(c, 0.9)),
    "sheet_1x2_a": (1, 2, lambda c: net(c, 1.0)), "sheet_1x2_b": (1, 2, lambda c: net(c, 1.2, reach=(0.5, 0.95))),
    "sheet_2x2_a": (2, 2, lambda c: net(c, 1.0)), "sheet_2x2_b": (2, 2, lambda c: net(c, 1.1, film=0.9)),
    "sheet_3x2_a": (3, 2, lambda c: net(c, 1.0)), "sheet_3x2_b": (3, 2, lambda c: net(c, 0.9, film=0.9)),
    "sheet_torn_2x2_a": (2, 2, lambda c: net(c, 1.1, tears=3)), "sheet_torn_2x2_b": (2, 2, lambda c: net(c, 1.0, tears=4)),
    "sheet_frayed_3x2_a": (3, 2, lambda c: net(c, 1.0, reach=(0.35, 1.0), tears=3, frayed=True)),
    "canopy_a": (3, 3, canopy),
    # corners and floors (cave_vines)
    "fan_1_a": (1, 1, fan), "fan_1_b": (1, 1, fan), "fan_1_c": (1, 1, lambda c: fan(c, 0.9)),
    "fan_2_a": (2, 2, fan), "fan_2_b": (2, 2, lambda c: fan(c, 0.9)),
    "corner_net_a": (1, 2, span), "corner_net_b": (1, 2, lambda c: span(c, 1.3)),
    "tilt_net_a": (1, 1, lambda c: net(c, 1.0, reach=(0.9, 1.0))),
    "mat_a": (1.5, 1.5, mesh), "mat_b": (1.5, 1.5, lambda c: mesh(c, film=0.8)),
    "mat_tangle_a": (1.5, 1.5, lambda c: mesh(c, debris=1.0, scale=1.5)),
    "drape_a": (1.5, 1.5, lambda c: mesh(c, film=1.0, scale=1.2)), "drape_b": (1.5, 1.5, lambda c: mesh(c, film=0.7, scale=1.4)),
    # the rest
    "cocoon": (1, 1, lambda c: wrapped(c, np.array([188, 184, 166], float), 0.99)),
    "egg_sac": (1, 1, lambda c: wrapped(c, np.array([206, 202, 176], float), 0.96, SLIME * 0.9)),
    "slime_pool_a": (1.75, 1.75, pool), "slime_pool_b": (1.75, 1.75, pool),
}

# RP-Mordor's hand-painted webs, as more of the same: its corner webs' corner
# is at their top right, as fan()'s, and its 1x2s are hanging sheets
FROM_MORDOR = {
    "fan_1_m1": "web_1x1_1", "fan_1_m2": "web_1x1_2", "fan_1_m3": "web_1x1_3", "fan_1_m4": "web_1x1_5",
    "fan_2_m1": "web_2x2_1", "fan_2_m2": "web_2x2_3", "fan_2_m3": "web_2x2_5",
    "sheet_1x2_m1": "web_1x2s_1", "sheet_1x2_m2": "web_1x2s_3", "sheet_1x2_m3": "web_1x2s_5",
}


def main(argv):
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")] or list(TEXTURES) + list(FROM_MORDOR)
    for name in names:
        path = BLOCK / f"spiderweb_{name}.png"
        if path.exists() and not force:
            continue
        if name in FROM_MORDOR:
            Image.open(MORDOR / f"{FROM_MORDOR[name]}.png").convert("RGBA").save(path)
        else:
            w, h, paint = TEXTURES[name]
            c = Canvas(round(w * PX), round(h * PX), f"spiderweb_{name}")
            paint(c)
            c.image().save(path)
        print("painted", path.relative_to(PACK).as_posix())


if __name__ == "__main__":
    main(sys.argv[1:])
