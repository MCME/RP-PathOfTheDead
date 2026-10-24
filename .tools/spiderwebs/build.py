"""Builds Shelob's webs from their textures: the models, the blockstates of the
blocks they're placed as, their items and icons, and the Architect inventory
entries - and encodes the textures for the shaders (spiderweb.glsl).

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

The blocks: all three kinds of vine, which have no collision, give no light
(cave vines' berries do - those states aren't used), let a player climb as a
web would, and aren't used by the pack otherwise. Each age is one web, or one
facing of one.
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
FILLER = (188, 186, 174)
FIRST_CMD = 2518

# ------------------------------------------------------------------ weights
# Each texture's sway, by its name's start: how far, in blocks, a texel at
# (u, v) - 0 to 1 across and down it - hangs from where it's held, for a
# texture w by h blocks.


def hang(offset=0.0):
    return lambda u, v, w, h: offset + v * h


WEIGHTS = [
    ("extension_", hang(2.0)),                      # below a 2-block strand
    ("drop_", hang()), ("tangle_", hang()), ("slime_strand_", hang()), ("torn_", hang()),
    ("sheet_", hang()),
    ("sag_", lambda u, v, w, h: min(u, 1 - u) * w * 0.8 + v * h * 0.4),   # held at both ends
    ("guy_", lambda u, v, w, h: min(math.hypot(u * w, v * h), math.hypot((1 - u) * w, (1 - v) * h)) * 0.5),
    ("canopy_", lambda u, v, w, h: min(u, 1 - u, v, 1 - v) * w * 0.8),    # held all round
    ("fan_", lambda u, v, w, h: min(v * h, (1 - u) * w)),                # held at the top and right
    ("corner_net_", lambda u, v, w, h: min(u, 1 - u) * w * 1.5 + v * h * 0.3),
    ("tilt_net_", lambda u, v, w, h: min(v, 1 - v) * h),
    ("mat_", lambda u, v, w, h: 0.5), ("drape_", lambda u, v, w, h: 0.5),   # only shivers
    ("cocoon", lambda u, v, w, h: 0.5),
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
        bw, bh = w / 32.0, h / 32.0
        level = np.zeros((h, w), np.int32)
        for y in range(h):
            for x in range(w):
                level[y, x] = min(7, max(0, round(f((x + 0.5) / w, (y + 0.5) / h, bw, bh) * 2.0)))
        for bit, channel in enumerate((0, 1, 2)):
            image[..., channel] = (image[..., channel] & ~4) | (((level >> bit) & 1) << 2)
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
    return {"angle": angle, "axis": axis, "origin": list(origin), "rescale": rescale}


def cross(tex, y0, y1, nv):
    """Two planes crossed through the block's middle, as a plant's."""
    return (plane("z", 8, (0, 16), (y0, y1), tex, n=(1, nv), rot=turn("y", 45, (8, 8, 8)))
            + plane("z", 8, (0, 16), (y0, y1), tex, n=(1, nv), rot=turn("y", -45, (8, 8, 8))))


def box(frm, to, tex, rot=None):
    faces = {f: {"uv": [0, 0, 16, 16], "texture": tex} for f in ("north", "east", "south", "west", "up", "down")}
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


# ---------------------------------------------------------------- catalogue
# id: display name, block, its ages (one for a web placed as itself, four for
# one placed by the way the builder faces: north, east, south, west - two for
# one along either axis: north-south, east-west), the textures each of its
# models takes (lists of variants, paired up), and its elements.



def T(i):
    return f"#t{i}"


CATALOGUE = [
    # ---- strands: weeping vines, hanging from the ceiling
    ("strand_drop_1", "Web Strand", "weeping_vines", [0], [["drop_1_a", "drop_1_b", "drop_1_c"]],
     lambda: cross(T(0), 0, 16, 3)),
    ("strand_drop_2", "Web Strand (2 Tall)", "weeping_vines", [1], [["drop_2_a", "drop_2_b", "drop_2_c"]],
     lambda: cross(T(0), -16, 16, 5)),
    ("strand_extension", "Web Strand Extension (below a strand)", "weeping_vines", [2], [["extension_a", "extension_b"]],
     lambda: cross(T(0), -16, 0, 3)),
    ("strand_tangle", "Web Strand Tangle", "weeping_vines", [3], [["tangle_a", "tangle_b"], ["tangle_b", "tangle_a"]],
     lambda: cross(T(0), -16, 16, 5) + plane("z", 8, (0, 16), (-16, 16), T(1), n=(1, 5), rot=turn("y", 22.5, (8, 8, 8), False))),
    ("strand_slime", "Slime-Laden Strand", "weeping_vines", [4], [["slime_strand_a", "slime_strand_b"]],
     lambda: cross(T(0), -16, 16, 5)),
    ("strand_sag_2", "Web Strand Slung (2 Wide)", "weeping_vines", [5, 6, 7, 8], [["sag_2_a", "sag_2_b"]],
     lambda: plane("x", 8, (16, -16), (-8, 16), T(0), n=(4, 2))),
    ("strand_sag_3", "Web Strand Slung (3 Wide)", "weeping_vines", [9, 10], [["sag_3_a", "sag_3_b"]],
     lambda: plane("x", 8, (32, -16), (-16, 16), T(0), n=(6, 3))),
    ("strand_sag_diagonal", "Web Strand Slung Diagonally", "weeping_vines", [11, 12, 13, 14], [["sag_diagonal_a"]],
     lambda: plane("z", 0, (0, 32), (0, 16), T(0), n=(4, 2), rot=turn("y", 45, (16, 8, 0)))),
    ("strand_guy", "Web Guy Line (to the floor ahead)", "weeping_vines", [15, 16, 17, 18], [["guy_a", "guy_b"]],
     lambda: plane("x", 8, (8, -16), (-16, 16), T(0), n=(3, 4))),
    ("strand_torn", "Torn Web Strands", "weeping_vines", [19], [["torn_a", "torn_b"]],
     lambda: cross(T(0), 0, 16, 2)),
    # ---- sheets: twisting vines, hung across in front of the builder
    ("sheet_1x1", "Web Sheet", "twisting_vines", [0, 1], [["sheet_1x1_a", "sheet_1x1_b"]],
     lambda: plane("z", 8, (0, 16), (0, 16), T(0), n=(2, 2))),
    ("sheet_1x2", "Web Sheet (2 Tall)", "twisting_vines", [2, 3], [["sheet_1x2_a", "sheet_1x2_b", "sheet_1x2_m1", "sheet_1x2_m2", "sheet_1x2_m3"]],
     lambda: plane("z", 8, (0, 16), (-16, 16), T(0), n=(2, 4))),
    ("sheet_2x2", "Web Sheet (2x2)", "twisting_vines", [4, 5], [["sheet_2x2_a", "sheet_2x2_b"]],
     lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4))),
    ("sheet_3x2", "Web Sheet (3 Wide)", "twisting_vines", [6, 7], [["sheet_3x2_a", "sheet_3x2_b"]],
     lambda: plane("z", 8, (-16, 32), (-16, 16), T(0), n=(4, 4))),
    ("sheet_torn_2x2", "Torn Web Sheet", "twisting_vines", [8, 9], [["sheet_torn_2x2_a", "sheet_torn_2x2_b"]],
     lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4))),
    ("sheet_frayed_3x2", "Frayed Web Curtain", "twisting_vines", [10, 11], [["sheet_frayed_3x2_a"]],
     lambda: plane("z", 8, (-16, 32), (-16, 16), T(0), n=(4, 4))),
    ("sheet_diagonal_1x2", "Web Sheet Diagonal", "twisting_vines", [12, 13], [["sheet_1x2_a", "sheet_1x2_b", "sheet_1x2_m2"]],
     lambda: plane("z", 8, (0, 16), (-16, 16), T(0), n=(2, 4), rot=turn("y", 45, (8, 8, 8)))),
    ("sheet_diagonal_2x2", "Web Sheet Diagonal (2x2)", "twisting_vines", [14, 15], [["sheet_2x2_a", "sheet_2x2_b"]],
     lambda: plane("z", 8, (-8, 24), (-16, 16), T(0), n=(3, 4), rot=turn("y", 45, (8, 8, 8)))),
    ("sheet_canopy", "Web Canopy (under a ceiling)", "twisting_vines", [16], [["canopy_a"]],
     lambda: plane("y", 13, (-16, 32), (-16, 32), T(0), n=(4, 4))),
    # ---- corners and floors: cave vines, against the wall in front
    ("corner_ceiling", "Corner Web (wall to ceiling)", "cave_vines", [0, 1, 2, 3],
     [["fan_1_a", "fan_1_b", "fan_1_m1", "fan_1_m2"], ["fan_1_m3", "fan_1_c", "fan_1_m4", "fan_1_a"], ["tilt_net_a"]],
     lambda: fans_on_north(T(0), T(1), 1)
     + plane("z", 5, (0, 16), (6, 16), T(2), n=(2, 2), rot=turn("x", 45, (8, 11, 5)))),
    ("corner_ceiling_large", "Corner Web Large (wall to ceiling)", "cave_vines", [4, 5, 6, 7],
     [["fan_2_a", "fan_2_b", "fan_2_m1"], ["fan_2_m2", "fan_2_m3", "fan_2_a"], ["tilt_net_a"]],
     lambda: fans_on_north(T(0), T(1), 2)
     + plane("z", 10, (-8, 24), (-4, 16), T(2), n=(3, 2), rot=turn("x", 45, (8, 6, 10)))),
    ("corner_wall", "Corner Web (between walls, front left)", "cave_vines", [8, 9, 10, 11],
     [["corner_net_a", "corner_net_b"], ["corner_net_b", "corner_net_a"]],
     lambda: plane("z", 3, (0, 6), (-16, 16), T(0), n=(1, 4), rot=turn("y", 45, (3, 0, 3)))
     + plane("z", 6.5, (0, 13), (-16, 16), T(1), n=(2, 4), rot=turn("y", 45, (6.5, 0, 6.5)))),
    ("corner_room", "Room Corner Web (front left, at the ceiling)", "cave_vines", [12, 13, 14, 15],
     [["fan_1_a", "fan_1_m1", "fan_1_b"], ["fan_1_m2", "fan_1_c", "fan_1_m3"], ["corner_net_a", "corner_net_b"]],
     lambda: plane("x", 3, (0, 16), (0, 16), T(0), u=(16, 0), n=(2, 2))
     + plane("z", 3, (0, 16), (0, 16), T(1), u=(16, 0), n=(2, 2))
     + plane("z", 5, (0, 10), (0, 16), T(2), n=(2, 2), rot=turn("y", 45, (5, 0, 5)))),
    ("corner_floor", "Corner Web (wall to floor)", "cave_vines", [16, 17, 18, 19],
     [["fan_1_b", "fan_1_m2", "fan_1_a"], ["fan_1_c", "fan_1_m4", "fan_1_m1"], ["tilt_net_a"]],
     lambda: fans_on_north(T(0), T(1), 1, floor=True)
     + plane("z", 5, (0, 16), (0, 10), T(2), n=(2, 2), rot=turn("x", -45, (8, 5, 5)))),
    ("floor_mat", "Web Mat (floor)", "cave_vines", [20], [["mat_a", "mat_b"]],
     lambda: plane("y", 0.2, (-4, 20), (-4, 20), T(0), n=(2, 2))),
    ("floor_tangle", "Web Tangle (floor)", "cave_vines", [21], [["mat_tangle_a"], ["tilt_net_a"]],
     lambda: plane("y", 0.35, (-4, 20), (-4, 20), T(0), n=(2, 2))
     + plane("z", 8, (2, 14), (0, 6), T(1), rot=turn("y", 22.5, (8, 0, 8), False))
     + plane("z", 5, (3, 11), (0, 4), T(1), rot=turn("y", -45, (7, 0, 5), False))),
    ("wall_drape", "Web Drape (on the wall in front)", "cave_vines", [22, 23, 24, 25], [["drape_a", "drape_b"]],
     lambda: plane("z", 0.25, (-4, 20), (-4, 20), T(0), n=(2, 2), faces=("south",))),
    # ---- the rest: the vines' stems, one state each
    ("cocoon", "Cocoon (a victim, wrapped)", "cave_vines_plant", None, [["cocoon"], ["drop_1_c"]],
     lambda: [box((5, -10, 5), (11, 8, 11), T(0), turn("y", 22.5, (8, 0, 8), False)),
              box((6, 8, 6), (10, 11, 10), T(0), turn("y", 22.5, (8, 0, 8), False)),
              box((6, -14, 6), (10, -10, 10), T(0), turn("y", 22.5, (8, 0, 8), False))]
     + cross(T(1), 10, 16, 1)),
    ("egg_sac", "Egg Sacs (under a ceiling)", "weeping_vines_plant", None, [["egg_sac"]],
     lambda: [box((3, 10, 3), (9, 16, 9), T(0)), box((8, 8, 7), (14, 15, 13), T(0)), box((5, 5, 9), (10, 11, 14), T(0))]),
    ("slime_pool", "Slime Pool", "twisting_vines_plant", None, [["slime_pool_a", "slime_pool_b"]],
     lambda: plane("y", 0.1, (-6, 22), (-6, 22), T(0), faces=("up",))),
]

# ...where in the inventory's collection each goes: strands, sheets, corners
# and floors a row each, the rest on the row above
SLOTS = {
    "strand_drop_2": "A0", "strand_drop_1": "A2", "strand_extension": "B2", "strand_tangle": "C2", "strand_slime": "D2",
    "strand_sag_2": "E2", "strand_sag_3": "F2", "strand_sag_diagonal": "G2", "strand_guy": "H2", "strand_torn": "I2",
    "sheet_1x1": "A3", "sheet_1x2": "B3", "sheet_2x2": "C3", "sheet_3x2": "D3", "sheet_torn_2x2": "E3",
    "sheet_frayed_3x2": "F3", "sheet_diagonal_1x2": "G3", "sheet_diagonal_2x2": "H3", "sheet_canopy": "I3",
    "corner_ceiling": "A4", "corner_ceiling_large": "B4", "corner_wall": "C4", "corner_room": "D4", "corner_floor": "E4",
    "floor_mat": "F4", "floor_tangle": "G4", "wall_drape": "H4", "cocoon": "A1", "egg_sac": "E1", "slime_pool": "F1",
}
HEAD = "strand_drop_2"

AGES = 26


def state_key(block, age):
    return f"age={age},berries=false" if block == "cave_vines" else f"age={age}"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def check_bounds(name, elements):
    for e in elements:
        for c in e["from"] + e["to"]:
            if not -16 <= c <= 32:
                raise ValueError(f"{name}: {c} is outside a model's -16 to 32")


def build():
    used = sorted({t for *_, textures, _ in CATALOGUE for vs in textures for t in vs})
    for t in used:
        encode(t)

    models = ASSETS / "models/block/spiderweb"
    states = {}   # block -> {key: [variants]}
    for wid, _, block, ages, textures, elements in CATALOGUE:
        els = elements()
        check_bounds(wid, els)
        count = len(textures)
        first = textures[0][0]
        write_json(models / f"{wid}.json", {
            "ambientocclusion": False,
            "textures": {"particle": T(0)},
            "elements": els,
        })
        variants = []
        for k in range(max(len(vs) for vs in textures)):
            vname = f"{wid}_{k + 1}"
            write_json(models / f"{vname}.json", {
                "parent": f"minecraft:block/spiderweb/{wid}",
                "textures": {f"t{i}": f"minecraft:block/spiderweb_{textures[i][k % len(textures[i])]}" for i in range(count)},
            })
            variants.append(f"minecraft:block/spiderweb/{vname}")
        table = states.setdefault(block, {})
        if ages is None:
            # one state: every variant, each turned all four ways
            key = "berries=false" if block == "cave_vines_plant" else ""
            table[key] = [{"model": m, "y": y} if y else {"model": m} for m in variants for y in (0, 90, 180, 270)]
        elif len(ages) == 1:
            table[state_key(block, ages[0])] = [{"model": m, "y": y} if y else {"model": m}
                                                for m in variants for y in (0, 90, 180, 270)]
        else:
            turns = (0, 90, 180, 270) if len(ages) == 4 else (0, 90)
            for age, y in zip(ages, turns):
                table[state_key(block, age)] = [{"model": m, "y": y} if y else {"model": m} for m in variants]

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

    write_items()
    write_inventory()
    print(f"{len(used)} textures encoded, {len(CATALOGUE)} webs")


# --------------------------------------------------------------------- items

def icon(wid, texture):
    """The inventory's icon: the web's first texture, fitted into 32x32 and
    made plain enough to see at that size."""
    image = Image.open(TEXTURES / f"spiderweb_{texture}.png").convert("RGBA")
    scale = 32.0 / max(image.size)
    small = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.BOX)
    a = np.array(small).astype(np.float64)
    a[..., 3] = np.where(a[..., 3] < 24, 0, np.minimum(255, a[..., 3] * 1.8))
    out = Image.new("RGBA", (32, 32))
    small = Image.fromarray(a.astype(np.uint8), "RGBA")
    out.alpha_composite(small, ((32 - small.width) // 2, (32 - small.height) // 2))
    path = ASSETS / f"textures/item/spiderweb_{wid}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


ENTRY = ('{nl}            {{{nl}                "threshold": {cmd},{nl}                "model": {{{nl}'
         '                    "type": "model",{nl}                    "model": "item/spiderweb/{wid}"{nl}'
         '                }}{nl}            }}')


def write_items():
    """The icons, their item models, and their entries in clay_ball.json from
    FIRST_CMD on - written over its own earlier ones, the rest of the file
    left as it is."""
    for k, (wid, _, _, _, textures, _) in enumerate(CATALOGUE):
        icon(wid, textures[0][0])
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
    text = text[:end + 1] + "," + entries.lstrip(",") + text[end + 1:]
    path.write_text(text, encoding="utf-8", newline="")


def write_inventory():
    """The webs' entries for RP-Inventories' Paths of the Dead inventory, in
    its det.yml: one collection, headed by the 2-block strand."""
    face = {4: ("North", "East", "South", "West"), 2: ("North", "East", "South", "West")}
    lines = ["  # Shelob's webs (RP-PathOfTheDead/.tools/spiderwebs/build.py)"]
    for k, (wid, display, block, ages, _, _) in enumerate(CATALOGUE):
        lines += [f"  spiderweb_{wid}:", "    itemMaterial: CLAY_BALL", f"    cmd: {FIRST_CMD + k}",
                  f"    display: {display}"]
        if wid == HEAD:
            lines.append("    category: Det")
        if ages is None or len(ages) == 1:
            if ages is None:
                data = f"minecraft:{block}[berries=false]" if block == "cave_vines_plant" else f"minecraft:{block}"
            else:
                data = f"minecraft:{block}[{state_key(block, ages[0])}]"
            lines += ["    type: BLOCK", f"    blockData: {data}"]
        else:
            lines.append("    type: FOUR_DIRECTIONS")
            picks = ages if len(ages) == 4 else (ages[0], ages[1], ages[0], ages[1])
            for side, age in zip(face[len(ages)], picks):
                lines.append(f"    blockData{side}: minecraft:{block}[{state_key(block, age)}]")
        lines.append("    collection:")
        if wid == HEAD:
            lines += [f"      {SLOTS[w]}: spiderweb_{w}" for w, *_ in CATALOGUE]
        else:
            lines.append(f"      indirect: spiderweb_{HEAD}")
    (Path(__file__).parent / "inventory.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
