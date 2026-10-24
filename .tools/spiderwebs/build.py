"""Builds Shelob's webs from their textures: the models, the blockstates of the
blocks they're placed as, their items and icons, the Architect inventory
entries, and the textures' entries in .mcme-shaders.json - and encodes the
textures for the shaders (spiderweb.glsl).

    python .tools/spiderwebs/build.py
    python <ResourcePackScripts>/generateVanilla/syncShaderBase.py .

Run it after any edit of a spiderweb_*.png, then the sync, which signs them as
the web (and slime) fluid kinds: the signature is in each texel's lowest two
bits of red, green and blue, which this leaves alone. What this writes into a
texture, every time, so that it doesn't matter where the texture came from:

- no texel fully transparent nor fully opaque: alpha from 2 to 253. A texel
  of alpha 0 can't carry the signature, and one of 255 or 0 would put the web
  kind's code into the solid or cutout pass, slowing every face there
  (mcme_pass.glsl). 2 is less than either translucent pass keeps, so the
  empty texels stay unseen with or without the shaders, and 254 is objmc's.
  The empty ones take the silk's colour, so that mipmaps don't darken it.
- in bit 2 of red, green and blue, how far each texel hangs from what holds it
  (0 to 7, in half blocks), which the vertex shader reads at each corner of a
  face to sway it by: WEIGHTS below, by texture. It shifts no colour by more
  than 4 steps in 255.

Every face is mapped at 16 texels a block, as the rest of the pack: a texture
is the size, in texels, of the faces it's on, in model units - turned and
rescaled ones' as they're drawn. The build stops on a face that isn't.

The blocks: the vines, which have no collision, give no light (cave vines'
berries do - those states aren't used), let a player climb as a web would,
and aren't used by the pack otherwise. Each age of weeping, twisting and cave
vines is one web, or one facing of one. Plain vines are the corner webs, as
Human's and Mordor's beams: each of its sides - north, east, south, west -
webbed or not, at the ceiling (up=false) or the floor (up=true); placed
facing a wall, then shift+right-clicked from another side to web that side
too, or clear it (FOUR_DIRECTIONS_COMPLEX).
"""

import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

PACK = Path(__file__).resolve().parents[2]
ASSETS = PACK / "assets/minecraft"
TEXTURES = ASSETS / "textures/block"
PX = 16          # texels a block
FILLER = (188, 186, 174)
FIRST_CMD = 2518
ROOT2 = math.sqrt(2.0)

# ------------------------------------------------------------------ weights
# Each texture's sway, by its name's start: how far, in blocks, a texel at
# (u, v) - 0 to 1 across and down it - hangs from where it's held, for a
# texture w by h blocks.


def hang(offset=0.0):
    return lambda u, v, w, h: offset + v * h


def span(u, v, w, h):   # held at the left and right, and a little at the top
    return min(u, 1 - u) * w * 1.5 + v * h * 0.3


WEIGHTS = [
    ("extension_", hang(2.0)),                      # below a 2-block strand
    ("drop_", hang()), ("tangle_", hang()), ("slime_strand_", hang()), ("torn_", hang()),
    ("tuft_hang_", hang()), ("cocoon_strand", hang()), ("sheet_", hang()),
    ("sag_", lambda u, v, w, h: min(u, 1 - u) * w * 0.8 + v * h * 0.4),   # held at both ends
    ("guy_", lambda u, v, w, h: min(math.hypot(u * w, v * h), math.hypot((1 - u) * w, (1 - v) * h)) * 0.5),
    ("canopy_", lambda u, v, w, h: min(u, 1 - u, v, 1 - v) * w * 0.8),    # held all round
    ("fan_", lambda u, v, w, h: min(v * h, (1 - u) * w)),                # held at the top and right
    ("inner_net_", span), ("corner_net_", span),
    ("tilt_net_", lambda u, v, w, h: min(v, 1 - v) * h),                 # held at the top and bottom
    ("mat_", lambda u, v, w, h: 0.5), ("drape_", lambda u, v, w, h: 0.5), ("tuft_", lambda u, v, w, h: 0.5),
    ("cocoon", lambda u, v, w, h: 0.5),            # only shivers
    ("egg_sac", lambda u, v, w, h: 0.0),
    ("slime_pool_", None),                          # the slime: doesn't sway
]


def weight_of(name):
    for prefix, f in WEIGHTS:
        if name.startswith(prefix):
            return f
    raise KeyError(f"spiderweb_{name}: no weight for it in WEIGHTS")


def encode(name):
    path = TEXTURES / f"spiderweb_{name}.png"
    image = np.array(Image.open(path).convert("RGBA")).astype(np.int32)
    h, w = image.shape[:2]
    empty = image[..., 3] == 0
    image[empty, :3] = FILLER
    image[..., 3] = np.clip(image[..., 3], 2, 253)
    f = weight_of(name)
    if f is not None:
        bw, bh = w / PX, h / PX
        level = np.zeros((h, w), np.int32)
        for y in range(h):
            for x in range(w):
                level[y, x] = min(7, max(0, round(f((x + 0.5) / w, (y + 0.5) / h, bw, bh) * 2.0)))
        for bit in range(3):
            image[..., bit] = (image[..., bit] & ~4) | (((level >> bit) & 1) << 2)
    Image.fromarray(image.astype(np.uint8), "RGBA").save(path)


# ------------------------------------------------------------------- planes
# A plane is an element of no thickness, cut into n pieces across and down, so
# that the vertex shader can bend it: each piece's corners sway by their own
# weights. Every piece of it maps the texture onto the same place, from both
# sides, so that its faces' corners agree on their weights and move as one.


def plane(axis, at, a, b, tex, u=None, v=None, n=(1, 1), rot=None, faces=None):
    """A plane at axis = at, over a (x, or z for axis x) and b (y, or z for
    axis y), both (from, to). u and v: the a and b at which the texture's
    left and right, top and bottom are (by default its left at a's from, its
    top at b's to - or for axis y, at b's from, the north)."""
    u = u or (a[0], a[1])
    v = v or ((b[0], b[1]) if axis == "y" else (b[1], b[0]))
    U = lambda p: round(16.0 * (p - u[0]) / (u[1] - u[0]), 4)
    V = lambda p: round(16.0 * (p - v[0]) / (v[1] - v[0]), 4)
    faces = faces or {"x": ("east", "west"), "y": ("up", "down"), "z": ("south", "north")}[axis]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            a0, a1 = a[0] + (a[1] - a[0]) * i / n[0], a[0] + (a[1] - a[0]) * (i + 1) / n[0]
            b0, b1 = b[0] + (b[1] - b[0]) * j / n[1], b[0] + (b[1] - b[0]) * (j + 1) / n[1]
            lo_a, hi_a, lo_b, hi_b = min(a0, a1), max(a0, a1), min(b0, b1), max(b0, b1)
            # each face's uv: [left, top, right, bottom] as its viewer sees it
            uv = {
                "south": (U(lo_a), V(hi_b), U(hi_a), V(lo_b)),
                "north": (U(hi_a), V(hi_b), U(lo_a), V(lo_b)),
                "east": (U(hi_a), V(hi_b), U(lo_a), V(lo_b)),
                "west": (U(lo_a), V(hi_b), U(hi_a), V(lo_b)),
                "up": (U(lo_a), V(lo_b), U(hi_a), V(hi_b)),
                "down": (U(lo_a), V(hi_b), U(hi_a), V(lo_b)),
            }
            if axis == "z":
                frm, to = [lo_a, lo_b, at], [hi_a, hi_b, at]
            elif axis == "x":
                frm, to = [at, lo_b, lo_a], [at, hi_b, hi_a]
            else:
                frm, to = [lo_a, at, lo_b], [hi_a, at, hi_b]
            e = {"from": [round(c, 4) for c in frm], "to": [round(c, 4) for c in to],
                 "shade": False,
                 "faces": {f: {"uv": list(uv[f]), "texture": tex} for f in faces}}
            if rot:
                e["rotation"] = rot
            out.append(e)
    return out


def turn(axis, angle, origin, rescale=True):
    return {"angle": angle, "axis": axis, "origin": [round(c, 4) for c in origin], "rescale": rescale}


def cross(tex, y0, y1, nv):
    """Two planes crossed through the block's middle, as a plant's: each
    22.6 units across, as they're drawn."""
    return (plane("z", 8, (0, 16), (y0, y1), tex, n=(1, nv), rot=turn("y", 45, (8, 8, 8)))
            + plane("z", 8, (0, 16), (y0, y1), tex, n=(1, nv), rot=turn("y", -45, (8, 8, 8))))


def box(frm, to, tex, size, rot=None):
    """A box, each face showing as many texels of the texture (size, in
    texels) as it is units across - from a different place on it for each
    face, so that they don't repeat."""
    dx, dy, dz = (t - f for f, t in zip(frm, to))
    dims = {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy), "up": (dx, dz), "down": (dx, dz)}
    faces = {}
    for k, (f, (fw, fh)) in enumerate(dims.items()):
        ox = (k * 7 + int(frm[0] * 3 + frm[1])) % max(1, int(size[0] - fw) + 1)
        oy = (k * 5 + int(frm[2] * 3 + frm[1] * 2)) % max(1, int(size[1] - fh) + 1)
        su, sv = 16.0 / size[0], 16.0 / size[1]
        faces[f] = {"uv": [round(ox * su, 4), round(oy * sv, 4), round((ox + fw) * su, 4), round((oy + fh) * sv, 4)], "texture": tex}
    e = {"from": list(frm), "to": list(to), "faces": faces}
    if rot:
        e["rotation"] = rot
    return e


def fans_on_north(tex_a, tex_b, size, floor=False):
    """Corner webs between the north wall and the ceiling (or floor), across
    the corner's line: their texture's top right corner in the corner."""
    s = 16 * size
    y = (16 - s, 16)
    v = (y[0], y[1]) if floor else None    # floor: its top at the floor
    xs = (4, 12) if size == 1 else (2, 9, 14)
    out = []
    for k, x in enumerate(xs):
        out += plane("x", x, (0, s), y, tex_a if k % 2 == 0 else tex_b, u=(s, 0), v=v, n=(size + 1, size + 1))
    return out


def tilted(tex, length, x, floor=False, n=(2, 2)):
    """A plane cutting the corner between the north wall and the ceiling (or
    floor) at 45 degrees, length units from wall to ceiling as it's drawn."""
    a = length / ROOT2                 # how far along the wall, and the ceiling
    z = a / 2
    y = a / 2 if floor else 16 - a / 2
    return plane("z", z, x, (y - a / 2, y + a / 2), tex, n=n, rot=turn("x", -45 if floor else 45, (8, y, z)))


def across_corner(tex, length, y, n=(1, 4)):
    """A vertical plane across the inside corner of the north and west walls,
    length units from wall to wall as it's drawn."""
    a = length / ROOT2
    return plane("z", a / 2, (0, a), y, tex, n=n, rot=turn("y", 45, (a / 2, 0, a / 2)))


# ------------------------------------------------------------------- models
# id: the textures each takes (lists of variants, paired up: variant k takes
# the k-th of each, round again where a list is shorter), its elements - in
# terms of "#t0", "#t1", ...


def T(i):
    return f"#t{i}"


MODELS = {
    # ---- strands
    "strand_drop_1": ([["drop_1_a", "drop_1_b", "drop_1_c"]], lambda: cross(T(0), 0, 16, 3)),
    "strand_drop_2": ([["drop_2_a", "drop_2_b", "drop_2_c"]], lambda: cross(T(0), -16, 16, 5)),
    "strand_extension": ([["extension_a", "extension_b"]], lambda: cross(T(0), -16, 0, 3)),
    "strand_tangle": ([["tangle_a", "tangle_b"], ["tangle_side_a", "tangle_side_b"]],
                      lambda: cross(T(0), -16, 16, 5) + plane("z", 8, (0, 16), (-16, 16), T(1), n=(1, 5), rot=turn("y", 22.5, (8, 8, 8), False))),
    "strand_slime": ([["slime_strand_a", "slime_strand_b"]], lambda: cross(T(0), -16, 16, 5)),
    "strand_sag_2": ([["sag_2_a", "sag_2_b"]], lambda: plane("x", 8, (16, -16), (-8, 16), T(0), n=(4, 2))),
    "strand_sag_3": ([["sag_3_a", "sag_3_b"]], lambda: plane("x", 8, (32, -16), (-16, 16), T(0), n=(6, 3))),
    "strand_sag_diagonal": ([["sag_diagonal_a"]], lambda: plane("z", 0, (0, 32), (0, 16), T(0), n=(4, 2), rot=turn("y", 45, (16, 8, 0)))),
    "strand_guy": ([["guy_a", "guy_b"]], lambda: plane("x", 8, (8, -16), (-16, 16), T(0), n=(3, 4))),
    "strand_torn": ([["torn_a", "torn_b"]], lambda: cross(T(0), 0, 16, 2)),
    # ---- sheets
    "sheet_1x1": ([["sheet_1x1_a", "sheet_1x1_b"]], lambda: plane("z", 8, (0, 16), (0, 16), T(0), n=(2, 2))),
    "sheet_1x2": ([["sheet_1x2_a", "sheet_1x2_b", "sheet_1x2_m1", "sheet_1x2_m2", "sheet_1x2_m3"]],
                  lambda: plane("z", 8, (0, 16), (-16, 16), T(0), n=(2, 4))),
    "sheet_2x2": ([["sheet_2x2_a", "sheet_2x2_b"]], lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4))),
    "sheet_3x2": ([["sheet_3x2_a", "sheet_3x2_b"]], lambda: plane("z", 8, (-16, 32), (-16, 16), T(0), n=(4, 4))),
    "sheet_torn_2x2": ([["sheet_torn_2x2_a", "sheet_torn_2x2_b"]], lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4))),
    "sheet_frayed_3x2": ([["sheet_frayed_3x2_a"]], lambda: plane("z", 8, (-16, 32), (-16, 16), T(0), n=(4, 4))),
    "sheet_diagonal_1x2": ([["sheet_diag_1x2_a", "sheet_diag_1x2_b"]],
                           lambda: plane("z", 8, (0, 16), (-16, 16), T(0), n=(2, 4), rot=turn("y", 45, (8, 8, 8)))),
    "sheet_diagonal_2x2": ([["sheet_diag_2x2_a", "sheet_diag_2x2_b"]],
                           lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4), rot=turn("y", 45, (8, 8, 8)))),
    "sheet_canopy": ([["canopy_a"]], lambda: plane("y", 13, (-16, 32), (-16, 32), T(0), n=(4, 4))),
    # ---- the corner webs' parts (vine): a side's web, the inside corner's
    # where two sides next to each other are both webbed, and a tuft where
    # no side is - each as on the north side, the north-west corner
    "corner_ceiling_side": ([["fan_1_a", "fan_1_b", "fan_1_m1", "fan_1_m2"], ["fan_1_m3", "fan_1_c", "fan_1_m4", "fan_1_a"], ["tilt_net_a", "tilt_net_b"]],
                            lambda: fans_on_north(T(0), T(1), 1) + tilted(T(2), 16, (0, 16))),
    "corner_ceiling_inside": ([["inner_net_a", "inner_net_b"]], lambda: across_corner(T(0), 16, (0, 16), n=(2, 2))),
    "corner_ceiling_tuft": ([["tuft_hang_a"]], lambda: cross(T(0), 8, 16, 1)),
    "corner_floor_side": ([["fan_1_b", "fan_1_m2", "fan_1_a"], ["fan_1_c", "fan_1_m4", "fan_1_m1"], ["tilt_net_b", "tilt_net_a"]],
                          lambda: fans_on_north(T(0), T(1), 1, floor=True) + tilted(T(2), 16, (0, 16), floor=True)),
    "corner_floor_inside": ([["inner_net_b", "inner_net_a"]], lambda: across_corner(T(0), 16, (0, 16), n=(2, 2))),
    "corner_floor_tuft": ([["tuft_a"], ["tuft_b"]],
                          lambda: plane("z", 8, (2, 14), (0, 8), T(0), rot=turn("y", 22.5, (8, 0, 8), False))
                          + plane("z", 5, (3, 11), (0, 4), T(1), rot=turn("y", -45, (7, 0, 5), False))),
    # ---- corners and floors
    "corner_ceiling_large": ([["fan_2_a", "fan_2_b", "fan_2_m1"], ["fan_2_m2", "fan_2_m3", "fan_2_a"], ["tilt_net_large_a"]],
                             lambda: fans_on_north(T(0), T(1), 2) + tilted(T(2), 32, (-8, 24), n=(3, 3))),
    "corner_wall": ([["corner_net_s_a", "corner_net_s_b"], ["corner_net_l_a", "corner_net_l_b"]],
                    lambda: across_corner(T(0), 12, (-16, 16)) + across_corner(T(1), 20, (-16, 16), n=(2, 4))),
    "floor_mat": ([["mat_a", "mat_b"]], lambda: plane("y", 0.2, (-4, 20), (-4, 20), T(0), n=(2, 2))),
    "floor_tangle": ([["mat_tangle_a"], ["tuft_a"], ["tuft_b"]],
                     lambda: plane("y", 0.35, (-4, 20), (-4, 20), T(0), n=(2, 2))
                     + plane("z", 8, (2, 14), (0, 8), T(1), rot=turn("y", 22.5, (8, 0, 8), False))
                     + plane("z", 5, (3, 11), (0, 4), T(2), rot=turn("y", -45, (7, 0, 5), False))),
    "wall_drape": ([["drape_a", "drape_b"]], lambda: plane("z", 0.25, (-4, 20), (-4, 20), T(0), n=(2, 2), faces=("south",))),
    # ---- the rest
    "cocoon": ([["cocoon"], ["cocoon_strand"]],
               lambda: [box((5, -10, 5), (11, 8, 11), T(0), (32, 32), turn("y", 22.5, (8, 0, 8), False)),
                        box((6, 8, 6), (10, 11, 10), T(0), (32, 32), turn("y", 22.5, (8, 0, 8), False)),
                        box((6, -14, 6), (10, -10, 10), T(0), (32, 32), turn("y", 22.5, (8, 0, 8), False))]
               + cross(T(1), 8, 16, 1)),
    "egg_sac": ([["egg_sac"]], lambda: [box((3, 10, 3), (9, 16, 9), T(0), (32, 32)), box((8, 8, 7), (14, 15, 13), T(0), (32, 32)),
                                         box((5, 5, 9), (10, 11, 14), T(0), (32, 32))]),
    "slime_pool": ([["slime_pool_a", "slime_pool_b"]], lambda: plane("y", 0.1, (-6, 22), (-6, 22), T(0), faces=("up",))),
}

# ---------------------------------------------------------------- catalogue
# id: display name, block, how it's placed - its ages (one for a web placed
# as itself, four for one placed by the way the builder faces: north, east,
# south, west - two for one along either axis: north-south, east-west),
# None for a block of one state, or "ceiling"/"floor" for the corner webs on
# vines - and its model (the same id, unless said).

CATALOGUE = [
    # ---- strands: weeping vines, hanging from the ceiling
    ("strand_drop_1", "Web Strand", "weeping_vines", [0]),
    ("strand_drop_2", "Web Strand (2 Tall)", "weeping_vines", [1]),
    ("strand_extension", "Web Strand Extension (below a strand)", "weeping_vines", [2]),
    ("strand_tangle", "Web Strand Tangle", "weeping_vines", [3]),
    ("strand_slime", "Slime-Laden Strand", "weeping_vines", [4]),
    ("strand_sag_2", "Web Strand Slung (2 Wide)", "weeping_vines", [5, 6, 7, 8]),
    ("strand_sag_3", "Web Strand Slung (3 Wide)", "weeping_vines", [9, 10]),
    ("strand_sag_diagonal", "Web Strand Slung Diagonally", "weeping_vines", [11, 12, 13, 14]),
    ("strand_guy", "Web Guy Line (to the floor ahead)", "weeping_vines", [15, 16, 17, 18]),
    ("strand_torn", "Torn Web Strands", "weeping_vines", [19]),
    # ---- sheets: twisting vines, hung across in front of the builder
    ("sheet_1x1", "Web Sheet", "twisting_vines", [0, 1]),
    ("sheet_1x2", "Web Sheet (2 Tall)", "twisting_vines", [2, 3]),
    ("sheet_2x2", "Web Sheet (2x2)", "twisting_vines", [4, 5]),
    ("sheet_3x2", "Web Sheet (3 Wide)", "twisting_vines", [6, 7]),
    ("sheet_torn_2x2", "Torn Web Sheet", "twisting_vines", [8, 9]),
    ("sheet_frayed_3x2", "Frayed Web Curtain", "twisting_vines", [10, 11]),
    ("sheet_diagonal_1x2", "Web Sheet Diagonal", "twisting_vines", [12, 13]),
    ("sheet_diagonal_2x2", "Web Sheet Diagonal (2x2)", "twisting_vines", [14, 15]),
    ("sheet_canopy", "Web Canopy (under a ceiling)", "twisting_vines", [16]),
    # ---- corner webs: vines, a side at a time (shift+right-click the others)
    ("corner_ceiling", "Corner Webs (ceiling, shift+right-click a side)", "vine", "ceiling"),
    ("corner_floor", "Corner Webs (floor, shift+right-click a side)", "vine", "floor"),
    # ---- more corners, and floors: cave vines, against the wall in front
    ("corner_ceiling_large", "Corner Web Large (wall to ceiling)", "cave_vines", [4, 5, 6, 7]),
    ("corner_wall", "Corner Web (between walls, front left)", "cave_vines", [8, 9, 10, 11]),
    ("floor_mat", "Web Mat (floor)", "cave_vines", [20]),
    ("floor_tangle", "Web Tangle (floor)", "cave_vines", [21]),
    ("wall_drape", "Web Drape (on the wall in front)", "cave_vines", [22, 23, 24, 25]),
    # ---- the rest: the vines' stems, one state each
    ("cocoon", "Cocoon (a victim, wrapped)", "cave_vines_plant", None),
    ("egg_sac", "Egg Sacs (under a ceiling)", "weeping_vines_plant", None),
    ("slime_pool", "Slime Pool", "twisting_vines_plant", None),
]

# ...where in the inventory's collection each goes: strands, sheets, corners
# and floors a row each, the rest on the row above
SLOTS = {
    "strand_drop_2": "A0", "strand_drop_1": "A2", "strand_extension": "B2", "strand_tangle": "C2", "strand_slime": "D2",
    "strand_sag_2": "E2", "strand_sag_3": "F2", "strand_sag_diagonal": "G2", "strand_guy": "H2", "strand_torn": "I2",
    "sheet_1x1": "A3", "sheet_1x2": "B3", "sheet_2x2": "C3", "sheet_3x2": "D3", "sheet_torn_2x2": "E3",
    "sheet_frayed_3x2": "F3", "sheet_diagonal_1x2": "G3", "sheet_diagonal_2x2": "H3", "sheet_canopy": "I3",
    "corner_ceiling": "A4", "corner_floor": "B4", "corner_ceiling_large": "C4", "corner_wall": "D4",
    "floor_mat": "E4", "floor_tangle": "F4", "wall_drape": "G4", "cocoon": "A1", "egg_sac": "E1", "slime_pool": "F1",
}
HEAD = "strand_drop_2"
ICONS = {"corner_ceiling": "corner_ceiling_side", "corner_floor": "corner_floor_side"}

AGES = 26
SIDES = ("north", "east", "south", "west")
TURNS = {"north": 0, "east": 90, "south": 180, "west": 270}


def state_key(block, age):
    return f"age={age},berries=false" if block == "cave_vines" else f"age={age}"


def vine_state(sides, floor):
    return ",".join(f"{s}={'true' if s in sides else 'false'}" for s in SIDES) + f",up={'true' if floor else 'false'}"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))   # LF, on Windows too


def check(name, elements, textures):
    """That every element is where a model's can be, and every face shows a
    texel a unit - in each of the model's variants."""
    wrong = []
    for e in elements:
        for c in e["from"] + e["to"]:
            if not -16 <= c <= 32:
                wrong.append(f"{name}: {c} is outside a model's -16 to 32")
        d = [t - f for f, t in zip(e["from"], e["to"])]
        r = e.get("rotation")
        if r and r.get("rescale"):
            k = 1.0 / math.cos(math.radians(r["angle"]))
            for i, axis in enumerate("xyz"):
                if axis != r["axis"]:
                    d[i] *= k
        dims = {"north": (d[0], d[1]), "south": (d[0], d[1]), "east": (d[2], d[1]), "west": (d[2], d[1]),
                "up": (d[0], d[2]), "down": (d[0], d[2])}
        for f, face in e["faces"].items():
            u0, v0, u1, v1 = face["uv"]
            for variant in textures[int(face["texture"][2:])]:
                w, h = Image.open(TEXTURES / f"spiderweb_{variant}.png").size
                for units, texels in ((dims[f][0], abs(u1 - u0) * w / 16), (dims[f][1], abs(v1 - v0) * h / 16)):
                    if units > 0.5 and not 0.85 <= texels / units <= 1.18:
                        wrong.append(f"{name}: its {f} face shows {texels:.1f} texels of spiderweb_{variant} over {units:.1f} units")
    return wrong


def build():
    used = sorted({t for textures, _ in MODELS.values() for vs in textures for t in vs})
    for t in used:
        encode(t)
    for path in sorted(TEXTURES.glob("spiderweb_*.png")):
        if path.stem[len("spiderweb_"):] not in used:
            print(f"(no web uses {path.name})")

    # what this writes, it writes anew
    for folder, pattern in ((ASSETS / "models/block/spiderweb", "*.json"), (ASSETS / "models/item/spiderweb", "*.json"),
                            (ASSETS / "textures/item", "spiderweb_*.png")):
        for path in folder.glob(pattern):
            path.unlink()

    models = ASSETS / "models/block/spiderweb"
    variants = {}
    wrong = []
    for mid, (textures, elements) in MODELS.items():
        els = elements()
        wrong += check(mid, els, textures)
        write_json(models / f"{mid}.json", {"ambientocclusion": False, "textures": {"particle": T(0)}, "elements": els})
        variants[mid] = []
        for k in range(max(len(vs) for vs in textures)):
            vname = f"{mid}_{k + 1}"
            write_json(models / f"{vname}.json", {
                "parent": f"minecraft:block/spiderweb/{mid}",
                "textures": {f"t{i}": f"minecraft:block/spiderweb_{vs[k % len(vs)]}" for i, vs in enumerate(textures)},
            })
            variants[mid].append(f"minecraft:block/spiderweb/{vname}")
    if wrong:
        raise SystemExit("\n".join(wrong))

    def turned(mid, y, every=False):
        """Each of a model's variants, turned y degrees - or with every, each
        turned all four ways."""
        ys = (0, 90, 180, 270) if every else (y,)
        return [{"model": m, "y": t} if t else {"model": m} for m in variants[mid] for t in ys]

    states = {}   # block -> {key: [variants]}
    for wid, _, block, how in CATALOGUE:
        if block == "vine":
            continue
        table = states.setdefault(block, {})
        if how is None:
            table["berries=false" if block == "cave_vines_plant" else ""] = turned(wid, 0, True)
        elif len(how) == 1:
            table[state_key(block, how[0])] = turned(wid, 0, True)
        else:
            for age, y in zip(how, (0, 90, 180, 270) if len(how) == 4 else (0, 90)):
                table[state_key(block, age)] = turned(wid, y)

    # every state a vine can be in has a model: the ages no web has yet show
    # the first of the block's, and the cave vines' berries (which glow) the same
    # as without them
    for block in ("weeping_vines", "twisting_vines", "cave_vines"):
        table = states[block]
        fallback = next(iter(table.values()))
        for age in range(AGES):
            table.setdefault(state_key(block, age), fallback)
        if block == "cave_vines":
            for age in range(AGES):
                table[f"age={age},berries=true"] = table[state_key(block, age)]
    states["cave_vines_plant"]["berries=true"] = states["cave_vines_plant"]["berries=false"]

    def order(key):
        m = re.match(r"age=(\d+)(?:,berries=(\w+))?", key)
        return (int(m[1]), m[2] or "") if m else (-1, key)

    for block, table in states.items():
        write_json(ASSETS / f"blockstates/{block}.json",
                   {"variants": {k: (v[0] if len(v) == 1 else v) for k, v in sorted(table.items(), key=lambda kv: order(kv[0]))}})

    # the corner webs: a web on each webbed side, one across each inside
    # corner where both its sides are, a tuft where none is
    parts = []
    for layer, up in (("ceiling", "false"), ("floor", "true")):
        for side in SIDES:
            parts.append({"when": {side: "true", "up": up}, "apply": turned(f"corner_{layer}_side", TURNS[side])})
        for (a, b), y in ((("north", "west"), 0), (("north", "east"), 90), (("south", "east"), 180), (("south", "west"), 270)):
            parts.append({"when": {a: "true", b: "true", "up": up}, "apply": turned(f"corner_{layer}_inside", y)})
        parts.append({"when": {**{s: "false" for s in SIDES}, "up": up}, "apply": turned(f"corner_{layer}_tuft", 0, True)})
    write_json(ASSETS / "blockstates/vine.json", {"multipart": parts})

    write_items()
    write_inventory()
    write_fluids(used)
    print(f"{len(used)} textures encoded, {len(MODELS)} models, {len(CATALOGUE)} webs")


# --------------------------------------------------------------------- items

def icon(wid, texture):
    """The inventory's icon: the web's first texture, fitted into 16x16 and
    made plain enough to see at that size."""
    image = Image.open(TEXTURES / f"spiderweb_{texture}.png").convert("RGBA")
    scale = min(1.0, 16.0 / max(image.size))
    small = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.BOX)
    a = np.array(small).astype(np.float64)
    a[..., 3] = np.where(a[..., 3] < 24, 0, np.minimum(255, a[..., 3] * 1.6))
    out = Image.new("RGBA", (16, 16))
    small = Image.fromarray(a.astype(np.uint8), "RGBA")
    out.alpha_composite(small, ((16 - small.width) // 2, (16 - small.height) // 2))
    out.save(ASSETS / f"textures/item/spiderweb_{wid}.png")


ENTRY = ('{nl}            {{{nl}                "threshold": {cmd},{nl}                "model": {{{nl}'
         '                    "type": "model",{nl}                    "model": "item/spiderweb/{wid}"{nl}'
         '                }}{nl}            }}')


def write_items():
    """The icons, their item models, and their entries in clay_ball.json from
    FIRST_CMD on - written over its own earlier ones, the rest of the file
    left as it is."""
    for wid, *_ in CATALOGUE:
        icon(wid, MODELS[ICONS.get(wid, wid)][0][0][0])
        write_json(ASSETS / f"models/item/spiderweb/{wid}.json",
                   {"parent": "minecraft:item/generated", "textures": {"layer0": f"minecraft:item/spiderweb_{wid}"}})
    path = ASSETS / "items/clay_ball.json"
    text = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    text = re.sub(r',\s*\{\s*"threshold": \d+,\s*"model": \{\s*"type": "model",\s*"model": "item/spiderweb/[^"]+"\s*\}\s*\}', "", text)
    taken = [int(t) for t in re.findall(r'"threshold": (\d+)', text)]
    if taken and max(taken) >= FIRST_CMD:
        raise ValueError(f"clay_ball.json already has custom model data {max(taken)}: move FIRST_CMD past it")
    entries = ",".join(ENTRY.format(nl=nl, cmd=FIRST_CMD + k, wid=wid) for k, (wid, *_) in enumerate(CATALOGUE))
    end = text.rindex("}", 0, text.rindex("]"))
    path.write_bytes((text[:end + 1] + "," + entries + text[end + 1:]).encode("utf-8"))


# Architect's keys for a FOUR_DIRECTIONS_COMPLEX block's edits: the sides
# shift+right-clicked, as seen by a builder who placed it facing north
EDIT_KEYS = ["N", "E", "S", "W", "NW", "WS", "SE", "EN", "NS", "WE", "NWS", "WSE", "SEN", "ENW", "NWSE"]


def write_inventory():
    """The webs' entries for RP-Inventories' Paths of the Dead inventory, in
    its det.yml: one collection, headed by the 2-block strand."""
    lines = ["  # Shelob's webs (RP-PathOfTheDead/.tools/spiderwebs/build.py)"]
    for k, (wid, display, block, how) in enumerate(CATALOGUE):
        lines += [f"  spiderweb_{wid}:", "    itemMaterial: CLAY_BALL", f"    cmd: {FIRST_CMD + k}",
                  f"    display: {display}"]
        if wid == HEAD:
            lines.append("    category: Det")
        if block == "vine":
            # placed with the side faced webbed; each side shift+right-clicked
            # webbed or cleared: Architect turns the north table for the rest
            floor = how == "floor"
            lines.append("    type: FOUR_DIRECTIONS_COMPLEX")
            for side in SIDES:
                lines.append(f"    blockData{side.capitalize()}: minecraft:vine[{vine_state({side}, floor)}]")
            lines.append("    editDataNorth:")
            letters = dict(zip("NESW", SIDES))
            for key in EDIT_KEYS:
                webbed = {"north"} ^ {letters[c] for c in key}
                lines.append(f"      {key}: minecraft:vine[{vine_state(webbed, floor)}]")
        elif how is None or len(how) == 1:
            if how is None:
                data = f"minecraft:{block}[berries=false]" if block == "cave_vines_plant" else f"minecraft:{block}"
            else:
                data = f"minecraft:{block}[{state_key(block, how[0])}]"
            lines += ["    type: BLOCK", f"    blockData: {data}"]
        else:
            lines.append("    type: FOUR_DIRECTIONS")
            picks = how if len(how) == 4 else (how[0], how[1], how[0], how[1])
            for side, age in zip(SIDES, picks):
                lines.append(f"    blockData{side.capitalize()}: minecraft:{block}[{state_key(block, age)}]")
        lines.append("    collection:")
        if wid == HEAD:
            lines += [f"      {SLOTS[w]}: spiderweb_{w}" for w, *_ in CATALOGUE]
        else:
            lines.append(f"      indirect: spiderweb_{HEAD}")
    (Path(__file__).parent / "inventory.yml").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_fluids(used):
    """The webs' textures as this pack's own fluids, for the sync to sign:
    the slime 7, the rest 6."""
    path = PACK / ".mcme-shaders.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    fluids = {k: v for k, v in config.get("fluids", {}).items() if not k.startswith("spiderweb_")}
    for t in used:
        fluids[f"spiderweb_{t}"] = 7 if t.startswith("slime_pool_") else 6
    config["fluids"] = fluids
    path.write_bytes((json.dumps(config, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    build()
