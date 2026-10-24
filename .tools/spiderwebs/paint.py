"""Paints the spider webs' starting textures: Shelob's silk - grey cords, a
thin film between some, slime beading on them - procedurally, 16 texels a
block, as the rest of the pack is: each texture is the size, in texels, of
the faces it's mapped onto, in model units (build.py checks it).

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

SILK = np.array([214, 211, 198], float)
SILK_DARK = np.array([150, 148, 136], float)
SLIME = np.array([170, 178, 120], float)
SLIME_LIGHT = np.array([206, 210, 170], float)
HUSK = np.array([92, 84, 70], float)


class Canvas:
    """RGBA in floats, painted over: each stroke lies over what's there."""

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

    def cord(self, pts, alpha=0.85, shade=1.0, step=0.35):
        """A silk cord through pts, its brightness wandering along it."""
        seen = set()
        phase = self.rng.random() * 10.0
        length = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(d / step))
            for i in range(n + 1):
                t = i / n
                key = (int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)))
                if key in seen:
                    continue
                seen.add(key)
                v = 0.82 + 0.16 * math.sin((length + d * t) * 0.7 + phase) + 0.08 * self.rng.random()
                self.plot(key[0], key[1], np.clip(SILK * v * shade, 0, 255), alpha * (0.85 + 0.15 * self.rng.random()))
            length += d

    def bead(self, x, y):
        """A bead of slime caught on a cord."""
        self.plot(x, y, SLIME_LIGHT if self.rng.random() < 0.3 else SLIME, 0.92)

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
        for _ in range(self.rng.randint(1, 2)):
            x = cx + self.rng.uniform(-r, r) * 0.6
            y = cy - r * 0.8
            self.cord([(x, y), (x + self.rng.uniform(-1, 1), y + self.rng.uniform(2, r * 1.4))], alpha=0.75)

    def image(self):
        out = np.zeros((self.h, self.w, 4), np.uint8)
        out[..., :3] = np.clip(self.rgb, 0, 255).astype(np.uint8)
        out[..., 3] = np.clip(self.a * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(out, "RGBA")


def sag_line(p0, p1, sag, n=24):
    """From p0 to p1, sagging by sag texels at its middle."""
    return [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + sag * 4.0 * t * (1.0 - t))
            for t in (i / n for i in range(n + 1))]


def hanging(c, x, top, bottom, sway=0.6):
    """A cord hanging from top to bottom at about x, wavering."""
    f, ph = c.rng.uniform(0.15, 0.4), c.rng.random() * 6.3
    return [(x + sway * math.sin(y * f + ph) * (y - top) / max(bottom - top, 1), y)
            for y in np.linspace(top, bottom, max(2, int(bottom - top) + 1))]


def tip(c, x, y):
    """How a hanging cord ends: a glob of slime, a fray, or nothing."""
    k = c.rng.random()
    if k < 0.4:
        c.bead(x, y)
    elif k < 0.65:
        c.plot(x - 1, y + 1, SILK * 0.85, 0.6)


def beads_along(c, pts, share):
    for x, y in pts[2::4]:
        if c.rng.random() < share:
            c.bead(x, y)


# ------------------------------------------------------------------ the kinds

def drops(c, n, reach=(0.55, 1.0), main=True, start=0, slime=0.1):
    """Cords hanging from the top. With main, one down the middle to the bottom,
    for an extension below to go on from."""
    if main:
        pts = hanging(c, c.w // 2, start, c.h - 1, sway=0.3)
        c.cord(pts, alpha=0.95)
        beads_along(c, pts, slime)
    for _ in range(n):
        x = c.w / 2 + c.rng.uniform(-0.3, 0.3) * c.w
        bottom = c.h * c.rng.uniform(*reach) - 1
        pts = hanging(c, x, start, bottom)
        c.cord(pts, alpha=c.rng.uniform(0.7, 0.92))
        beads_along(c, pts, slime)
        tip(c, pts[-1][0], pts[-1][1])
        if c.rng.random() < 0.35:   # bridged to the middle cord near the top
            y = c.rng.uniform(1, c.h * 0.3)
            c.cord(sag_line((x, y), (c.w / 2, y + c.rng.uniform(-1, 1)), 1), alpha=0.7)


def sag(c, cords=3, drips=3):
    """Cords slung between the top corners, sagging, drips hanging off them."""
    lowest = None
    for i in range(cords):
        depth = c.h * (0.25 + 0.55 * (i + c.rng.random()) / cords)
        pts = sag_line((0, c.rng.uniform(0, 1)), (c.w - 1, c.rng.uniform(0, 1)), depth, n=48)
        c.cord(pts, alpha=0.9)
        beads_along(c, pts, 0.08)
        lowest = pts
    for _ in range(drips):
        x, y = lowest[c.rng.randint(8, len(lowest) - 9)]
        pts = hanging(c, x, y, min(c.h - 1, y + c.rng.uniform(2, 5)), sway=0.2)
        c.cord(pts, alpha=0.8)
        tip(c, pts[-1][0], pts[-1][1])


def guy(c):
    """A taut line from the top left down to the bottom right, splayed where
    it's fixed at either end."""
    pts = sag_line((0, 0), (c.w - 1, c.h - 1), 1.5, n=48)
    c.cord(pts, alpha=0.95)
    beads_along(c, pts, 0.1)
    for _ in range(2):
        a = pts[c.rng.randint(3, 10)]
        c.cord(sag_line(a, (c.rng.uniform(0, c.w * 0.5), 0), -0.5), alpha=0.7)
        b = pts[c.rng.randint(-10, -3)]
        c.cord(sag_line(b, (c.w - 1, c.rng.uniform(c.h * 0.6, c.h - 1)), 0.5), alpha=0.7)


def net(c, density=1.0, reach=(0.6, 1.0), tears=0, film=0.6):
    """Shelob's sheet: a cord along the top, cords hanging from it, wandering,
    threads slung between them every which way, a film over some of it."""
    top = sag_line((0, c.rng.uniform(0, 1)), (c.w - 1, c.rng.uniform(0, 1)), c.rng.uniform(0.5, 1.5), n=32)
    c.cord(top, alpha=0.95)
    n = max(2, int(c.w / 5 * density))
    lines = []
    for i in range(n):
        x = (i + 0.5 + c.rng.uniform(-0.4, 0.4)) * c.w / n
        bottom = c.h * c.rng.uniform(*reach) - 1
        pts = hanging(c, x, 1, bottom, sway=c.rng.uniform(0.8, 2.0))
        lines.append(pts)
        c.cord(pts, alpha=c.rng.uniform(0.7, 0.92))
        beads_along(c, pts, 0.06)
        tip(c, pts[-1][0], pts[-1][1])
    rungs = []
    for _ in range(int(c.w * c.h / 30 * density)):
        i = c.rng.randrange(len(lines) - 1)
        j = min(len(lines) - 1, i + 1 + (c.rng.random() < 0.3))
        a, b = lines[i], lines[j]
        ya = c.rng.uniform(0.05, 0.95) * (len(a) - 1)
        yb = min(len(b) - 1, max(0, ya + c.rng.uniform(-5, 5)))    # slanting, not a ladder
        p, q = a[int(ya)], b[int(yb)]
        c.cord(sag_line(p, q, c.rng.uniform(0.3, 2)), alpha=c.rng.uniform(0.5, 0.85))
        rungs.append((p, q))
    for _ in range(int(len(rungs) * film * 0.3)):
        (p, q), (r, s) = c.rng.sample(rungs, 2)
        if abs(p[0] - r[0]) < c.w / n * 1.6 and abs(p[1] - r[1]) < 8:
            c.film([p, q, s, r], alpha=c.rng.uniform(0.12, 0.24))
    for _ in range(tears):
        c.tear(c.rng.uniform(0.2, 0.8) * c.w, c.rng.uniform(0.35, 0.8) * c.h, c.rng.uniform(1.5, 3.5))


def fan(c, film=0.5):
    """A corner web: cords out from the top right corner, threads sagging
    across them in rings, a film where they're close."""
    corner = (c.w - 1, 0)
    r = min(c.w, c.h)
    n = c.rng.randint(4, 6) if r <= 16 else c.rng.randint(6, 8)
    spokes = []
    for i in range(n):
        a = (i + c.rng.uniform(-0.3, 0.3)) / (n - 1) * math.pi / 2
        length = r * c.rng.uniform(0.75, 1.15)
        end = (corner[0] - math.cos(a) * length, corner[1] + math.sin(a) * length)
        pts = sag_line(corner, end, c.rng.uniform(-0.5, 1))
        c.cord(pts, alpha=0.9)
        spokes.append(pts)
    for k, f in enumerate(sorted(c.rng.uniform(0.2, 0.95) for _ in range(c.rng.randint(2, 4) if r <= 16 else 5))):
        for i in range(n - 1):
            if c.rng.random() < 0.15:
                continue   # broken
            a, b = spokes[i], spokes[i + 1]
            p = a[min(len(a) - 1, int(f * len(a)))]
            q = b[min(len(b) - 1, int((f + c.rng.uniform(-0.05, 0.05)) * len(b)))]
            pts = sag_line(p, q, 0.5 + f)
            c.cord(pts, alpha=0.75)
            beads_along(c, pts, 0.05)
            if k == 0 and c.rng.random() < film:
                c.film([corner, p, q], alpha=0.18)
    s = spokes[c.rng.randrange(n)]   # a thread come loose at the rim
    x, y = s[-1]
    pts = hanging(c, x, y, min(c.h - 1, y + c.rng.uniform(2, 4)), 0.2)
    c.cord(pts, alpha=0.7)
    tip(c, pts[-1][0], pts[-1][1])


def span(c, density=1.0):
    """Between two walls: cords slung from the left edge to the right at
    every height, others hanging down between."""
    for i in range(int(c.h / 4 * density)):
        y = (i + c.rng.random()) * 4
        pts = sag_line((0, y), (c.w - 1, y + c.rng.uniform(-2, 2)), c.rng.uniform(0.5, 2.5), n=24)
        c.cord(pts, alpha=0.85)
        beads_along(c, pts, 0.06)
    drops(c, max(1, int(c.w / 6)), reach=(0.4, 0.9), main=False, slime=0.05)
    for _ in range(2):
        y = c.rng.uniform(0, c.h * 0.6)
        c.film([(0, y), (c.w - 1, y + 1), (c.w - 1, y + 5), (0, y + 4)], alpha=0.14)


def mesh(c, ragged=True, debris=0.0, film=0.5, scale=1.0):
    """A flat tangle, as a mat on the floor or silk plastered on a wall: short
    cords every which way, film over much of it, ragged at its rim."""
    cx, cy = c.w / 2, c.h / 2
    for _ in range(int(c.w * c.h / 14 * scale)):
        a = c.rng.random() * math.tau
        r = c.rng.random() ** 0.6 * c.w * 0.45
        p = (cx + math.cos(a) * r, cy + math.sin(a) * r)
        b = a + c.rng.uniform(-1.4, 1.4)
        length = c.rng.uniform(2, 7)
        q = (p[0] + math.cos(b) * length, p[1] + math.sin(b) * length)
        c.cord(sag_line(p, q, c.rng.uniform(-0.8, 0.8), n=8), alpha=c.rng.uniform(0.5, 0.85))
    for _ in range(int(6 * film)):
        a = c.rng.random() * math.tau
        r = c.rng.random() * c.w * 0.3
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        s = c.rng.uniform(2, 4)
        c.film([(x - s, y), (x, y - s * 0.8), (x + s, y + 1), (x, y + s * 0.9)], alpha=c.rng.uniform(0.14, 0.26))
    for _ in range(int(c.w * c.h / 60 * debris)):
        c.plot(cx + c.rng.uniform(-0.35, 0.35) * c.w, cy + c.rng.uniform(-0.35, 0.35) * c.h,
               HUSK * c.rng.uniform(0.8, 1.2), 0.9)
    for _ in range(int(c.w * c.h / 120)):
        c.bead(cx + c.rng.uniform(-0.3, 0.3) * c.w, cy + c.rng.uniform(-0.3, 0.3) * c.h)
    if ragged:
        ys, xs = np.mgrid[0:c.h, 0:c.w]
        ang = np.arctan2(ys - cy, xs - cx)
        rim = 0.38 + 0.06 * np.sin(ang * 3 + c.rng.random() * 6) + 0.04 * np.sin(ang * 7 + c.rng.random() * 6)
        d = np.hypot((xs + 0.5 - cx) / c.w, (ys + 0.5 - cy) / c.h)
        c.a *= np.clip((rim - d) / 0.08, 0.0, 1.0)


def canopy(c):
    """A sheet slung flat under a ceiling: a lattice of cords, jittered, film
    across some of it, holes worn through."""
    step = 6
    pts = {}
    for j in range(c.h // step + 2):
        for i in range(c.w // step + 2):
            pts[i, j] = (i * step + c.rng.uniform(-2, 2), j * step + c.rng.uniform(-2, 2))
    for (i, j), p in pts.items():
        for di, dj in ((1, 0), (0, 1), (1, 1)):
            q = pts.get((i + di, j + dj))
            if q and c.rng.random() < (0.8 if di + dj == 1 else 0.3):
                c.cord(sag_line(p, q, c.rng.uniform(-0.5, 0.5), n=8), alpha=c.rng.uniform(0.6, 0.9))
                r = pts.get((i, j + 1))
                if r and c.rng.random() < 0.25:
                    c.film([p, q, r], alpha=0.16)
    for _ in range(3):
        c.tear(c.rng.uniform(0.2, 0.8) * c.w, c.rng.uniform(0.2, 0.8) * c.h, c.rng.uniform(2, 3.5))


def wrapped(c, base, alpha, streaks=SLIME):
    """Silk wound round and round: a cocoon's skin, an egg sac's."""
    c.rgb[:] = base
    c.a[:] = alpha
    for _ in range(30):
        y = c.rng.uniform(-c.h, c.h)
        slope = c.rng.uniform(0.25, 0.7) * (1 if c.rng.random() < 0.5 else -1)
        c.cord([(x, y + x * slope) for x in np.linspace(0, c.w - 1, 16)], alpha=0.5, shade=c.rng.uniform(0.82, 1.1))
    for _ in range(3):
        for px, py in hanging(c, c.rng.uniform(0, c.w), c.rng.uniform(0, c.h * 0.5), c.h - 1, 0.6):
            c.plot(px, py, streaks, 0.4)


def pool(c):
    """A pool of slime: its outline only - the shaders draw the slime."""
    ys, xs = np.mgrid[0:c.h, 0:c.w]
    cx, cy = c.w / 2, c.h / 2
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    rim = 0.33 + 0.07 * np.sin(ang * 2 + c.rng.random() * 6) + 0.05 * np.sin(ang * 5 + c.rng.random() * 6)
    d = np.hypot((xs + 0.5 - cx) / c.w, (ys + 0.5 - cy) / c.h)
    c.rgb[:] = SLIME * 0.78
    c.a[:] = (d < rim) * 0.86
    for _ in range(4):   # smaller splashes round it
        a, r = c.rng.random() * math.tau, c.rng.uniform(0.38, 0.45)
        sx, sy = cx + math.cos(a) * r * c.w, cy + math.sin(a) * r * c.h
        c.a = np.maximum(c.a, (np.hypot(xs + 0.5 - sx, ys + 0.5 - sy) < c.rng.uniform(0.8, 1.5)) * 0.8)


def cord_strip(c):
    """The web lines' cords, wound along the texture: row 0 a thin one's
    faces, rows 2 and 3 a thick one's - lit above, darker below, slime beading
    on it here and there."""
    for x in range(c.w):
        v = 0.86 + 0.14 * math.sin(x * 0.9 + c.rng.random()) + 0.06 * c.rng.random()
        c.plot(x, 0, SILK * v, 0.95)
        c.plot(x, 2, SILK * v * 1.02, 0.97)
        c.plot(x, 3, SILK_DARK * v * 1.05, 0.97)
        if c.rng.random() < 0.08:
            c.bead(x, 2 + (c.rng.random() < 0.5))


# ---------------------------------------------------------------- the textures
# name: (width, height in texels - the faces' size in model units - painter)

def strand(n, **kw):
    return lambda c: drops(c, n, **kw)


TEXTURES = {
    # strands (weeping_vines): crossed planes, 22.6 units wide
    "drop_1_a": (24, 16, strand(1)), "drop_1_b": (24, 16, strand(2)), "drop_1_c": (24, 16, strand(1, slime=0.3)),
    "drop_2_a": (24, 32, strand(2)), "drop_2_b": (24, 32, strand(3, reach=(0.3, 0.9))), "drop_2_c": (24, 32, strand(2, slime=0.25)),
    "extension_a": (24, 16, strand(1, reach=(0.4, 0.9))), "extension_b": (24, 16, strand(1, reach=(0.6, 1.0), slime=0.3)),
    "tangle_a": (24, 32, strand(5, reach=(0.25, 1.0))), "tangle_b": (24, 32, strand(4, reach=(0.3, 0.8), slime=0.2)),
    "tangle_side_a": (16, 32, strand(3, reach=(0.3, 0.9), main=False)), "tangle_side_b": (16, 32, strand(2, reach=(0.4, 1.0), main=False)),
    "slime_strand_a": (24, 32, strand(2, slime=0.5)), "slime_strand_b": (24, 32, strand(2, slime=0.4)),
    "sag_2_a": (32, 24, lambda c: sag(c, 3, 3)), "sag_2_b": (32, 24, lambda c: sag(c, 2, 4)),
    "sag_3_a": (48, 32, lambda c: sag(c, 4, 4)), "sag_3_b": (48, 32, lambda c: sag(c, 3, 5)),
    "sag_diagonal_a": (44, 16, lambda c: sag(c, 3, 3)),
    "guy_a": (24, 32, guy), "guy_b": (24, 32, guy),
    "torn_a": (24, 16, strand(3, reach=(0.2, 0.7), main=False)), "torn_b": (24, 16, strand(2, reach=(0.3, 0.9), main=False, slime=0.3)),
    "tuft_hang_a": (24, 8, strand(2, reach=(0.5, 1.0), main=False)),
    # the web lines' cords (build.py's cords): each as long as its line, in
    # units - level 16, 45 degrees 22.6 or 27.7 on a diagonal, steep 35.8 or
    # 39.2, vertical 16 - and the anchors' (any length up to 40)
    "line_h": (16, 4, cord_strip), "line_d": (24, 4, cord_strip), "line_dd": (28, 4, cord_strip),
    "line_s": (36, 4, cord_strip), "line_sd": (40, 4, cord_strip), "line_v": (16, 4, cord_strip),
    "line_end": (40, 4, cord_strip),
    # sheets (twisting_vines)
    "sheet_1x1_a": (16, 16, lambda c: net(c, 1.2)), "sheet_1x1_b": (16, 16, lambda c: net(c, 1.0)),
    "sheet_1x2_a": (16, 32, lambda c: net(c, 1.0)), "sheet_1x2_b": (16, 32, lambda c: net(c, 1.2, reach=(0.5, 0.95))),
    "sheet_2x2_a": (32, 32, lambda c: net(c, 1.0)), "sheet_2x2_b": (32, 32, lambda c: net(c, 1.1, film=0.9)),
    "sheet_3x2_a": (48, 32, lambda c: net(c, 1.0)), "sheet_3x2_b": (48, 32, lambda c: net(c, 0.9, film=0.9)),
    "sheet_torn_2x2_a": (32, 32, lambda c: net(c, 1.1, tears=3)), "sheet_torn_2x2_b": (32, 32, lambda c: net(c, 1.0, tears=4)),
    "sheet_frayed_3x2_a": (48, 32, lambda c: net(c, 1.0, reach=(0.3, 1.0), tears=3)),
    "sheet_diag_1x2_a": (24, 32, lambda c: net(c, 1.0)), "sheet_diag_1x2_b": (24, 32, lambda c: net(c, 1.1, reach=(0.5, 0.95))),
    "sheet_diag_2x2_a": (44, 32, lambda c: net(c, 1.0)), "sheet_diag_2x2_b": (44, 32, lambda c: net(c, 1.0, film=0.9)),
    "canopy_a": (48, 48, canopy),
    # corners (vine, cave_vines) and floors (cave_vines)
    "fan_1_a": (16, 16, fan), "fan_1_b": (16, 16, fan), "fan_1_c": (16, 16, lambda c: fan(c, 0.9)),
    "fan_2_a": (32, 32, fan), "fan_2_b": (32, 32, lambda c: fan(c, 0.9)),
    "tilt_net_a": (16, 16, lambda c: net(c, 1.0, reach=(0.9, 1.0))), "tilt_net_b": (16, 16, lambda c: net(c, 1.2, reach=(0.85, 1.0))),
    "tilt_net_large_a": (32, 32, lambda c: net(c, 1.0, reach=(0.9, 1.0))),
    "inner_net_a": (16, 16, span), "inner_net_b": (16, 16, lambda c: span(c, 1.3)),
    "corner_net_s_a": (12, 32, span), "corner_net_s_b": (12, 32, lambda c: span(c, 1.3)),
    "corner_net_l_a": (20, 32, span), "corner_net_l_b": (20, 32, lambda c: span(c, 1.3)),
    "mat_a": (24, 24, mesh), "mat_b": (24, 24, lambda c: mesh(c, film=0.8)),
    "mat_tangle_a": (24, 24, lambda c: mesh(c, debris=1.0, scale=1.5)),
    "tuft_a": (12, 8, lambda c: net(c, 1.0, reach=(0.6, 1.0))), "tuft_b": (8, 4, lambda c: net(c, 1.0, reach=(0.8, 1.0))),
    "drape_a": (24, 24, lambda c: mesh(c, film=1.0, scale=1.2)), "drape_b": (24, 24, lambda c: mesh(c, film=0.7, scale=1.4)),
    # the rest
    "cocoon": (32, 32, lambda c: wrapped(c, np.array([188, 184, 166], float), 0.99)),
    "cocoon_strand": (24, 8, strand(0)),
    "egg_sac": (32, 32, lambda c: wrapped(c, np.array([206, 202, 176], float), 0.96, SLIME * 0.9)),
    "slime_pool_a": (28, 28, pool), "slime_pool_b": (28, 28, pool),
}

# RP-Mordor's hand-painted webs, as more of the same, halved to 16 texels a
# block: its corner webs' corner is at their top right, as fan()'s, and its
# 1x2s are hanging sheets
FROM_MORDOR = {
    "fan_1_m1": "web_1x1_1", "fan_1_m2": "web_1x1_2", "fan_1_m3": "web_1x1_3", "fan_1_m4": "web_1x1_5",
    "fan_2_m1": "web_2x2_1", "fan_2_m2": "web_2x2_3", "fan_2_m3": "web_2x2_5",
    "sheet_1x2_m1": "web_1x2s_1", "sheet_1x2_m2": "web_1x2s_3", "sheet_1x2_m3": "web_1x2s_5",
}


def halve(image):
    """Half the size, each 2x2 texels taking the most opaque of them, so that
    thin cords stay unbroken."""
    a = np.array(image.convert("RGBA"))
    h, w = a.shape[0] // 2, a.shape[1] // 2
    blocks = a[:h * 2, :w * 2].reshape(h, 2, w, 2, 4).transpose(0, 2, 1, 3, 4).reshape(h, w, 4, 4)
    pick = blocks[..., 3].argmax(-1)
    return Image.fromarray(np.take_along_axis(blocks, pick[..., None, None], 2)[:, :, 0], "RGBA")


def main(argv):
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")] or list(TEXTURES) + list(FROM_MORDOR)
    for name in names:
        path = BLOCK / f"spiderweb_{name}.png"
        if path.exists() and not force:
            continue
        if name in FROM_MORDOR:
            halve(Image.open(MORDOR / f"{FROM_MORDOR[name]}.png")).save(path)
        else:
            w, h, paint = TEXTURES[name]
            c = Canvas(w, h, f"spiderweb_{name}")
            paint(c)
            c.image().save(path)
        print("painted", path.relative_to(PACK).as_posix())


if __name__ == "__main__":
    main(sys.argv[1:])
