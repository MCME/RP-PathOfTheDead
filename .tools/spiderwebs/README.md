# Shelob's webs

Spider webs for Shelob's lair: free-hanging strands, chainable web lines, hanging sheets, corner and floor webs, cocoons, egg sacs and slime pools. Their shaders make them sway, shiver when someone is close, glisten, and drip slime (`assets/minecraft/shaders/include/spiderweb.glsl`). The wetness only ever brightens the silk's own lit colour. Nothing on a web gives off light.

This folder starts with a dot, so it never goes into a zip.

## Workflow

```
python .tools/spiderwebs/paint.py              # only once: placeholder art for any texture that's missing
python .tools/spiderwebs/build.py              # models, blockstates, items, icons, inventory.yml, fluid list; encodes textures
python <ResourcePackScripts>/generateVanilla/syncShaderBase.py .   # signs the textures, writes the 26.3 copies
```

Run `build.py`, then the sync, after **any** edit of a `textures/block/spiderweb_*.png`. The build also lists each texture in `.mcme-shaders.json`'s `fluids`: kind `6` for a web, `7` for slime.

## Textures

Every face is mapped at **16 texels per block**, like the rest of the pack. A texture is the size, in texels, of the faces it's mapped onto, in model units. For rotated planes that's their drawn size: a diagonal 1-block plane is 22.6 units wide, so its texture is 24 wide. `paint.py`'s `TEXTURES` table lists every size. The build stops on any face that shows more or fewer than 1 texel per unit (±15%).

Paint freely over the placeholder art. `build.py` handles the rest:

- **Alpha** is clamped to 2–253. Empty texels at alpha 2 stay invisible in every pass, and the web code compiles into the translucent pass only.
- **Bit 2 of red, green and blue** holds how far each texel hangs from its anchor, which drives the sway. Each texture's pattern comes from `WEIGHTS`, by name prefix: `hang`, held at the top; `sag_`, held at both ends; `fan_`, held at its top and right edges; `line_`, held at both joints; and so on.

## Web lines

Web lines chain and fork like Human's tree branches. They use Architect's own branch types, so the placement logic is the same:

| Item | Type | Shape |
|---|---|---|
| Web Line (level) | `BRANCH_HORIZONTAL` | 1 block across, 4 directions |
| Web Line (45 degrees) | `BRANCH_DIAGONAL` | up 1 over 1, 8 directions |
| Web Line (steep) | `BRANCH_STEEP` | up 2 over 1, 8 directions |
| Web Line (vertical) / (vertical, thick) | `BRANCH_TWIGS` | up its own block |
| Web Line Anchor | `BRANCH_TWIGS` | cords splayed to the ceiling above, or to the floor below |

- **Joints:** every line runs between joints at the middle of a block's top or bottom face, as the branch shift tables lay them out (`LINES`). A line placed on the floor starts there; one placed against a ceiling ends there.
- **Chaining and forking:** click a line's end to go on from it, in whatever direction you face. Click the same end again facing another way to fork.
- **Thin and thick:** shift+right-click a line to switch it between thin (1px) and thick (2px, slimed). A new line takes after the one it's chained to.
- **Anchors:** placed looking down onto a joint, an anchor splays up to the ceiling. Placed looking up under one, it splays down to the floor. Shift+right-click flips it.
- **Vertical runs:** build them upwards, by clicking a top. From the bottom of a vertical line, Architect would put the next one in the same block.

Each line is a real cord: a few thin boxes rotated to any angle (26.2's `x`/`y`/`z` element rotation), sagging a little between its joints. Both ends are held still, so chained lines stay joined while they sway.

## Blocks

| Block | States | What |
|---|---|---|
| `vine` | all 32 | Corner webs: each side webbed or not; `up=false` at the ceiling, `up=true` at the floor |
| `cave_vines` | age 0–25, berries=false | Web lines (berries=true would glow: shown, never placed) |
| `twisting_vines` | age 0–15 / 16–25 | Sheets / web lines |
| `weeping_vines` | age 0–19 / 20–25 | Strands / web lines |
| `oak_button` | floor, wall | Web line anchors |
| `birch_button` | all 12 | Large corner, wall corner, wall drape |
| `jungle_button` | floor north–south | Floor mat, floor tangle, canopy (9 free) |
| `cave_vines_plant` / `weeping_vines_plant` / `twisting_vines_plant` | — | Cocoon / egg sacs / slime pool |

None of these blocks has collision, and none was used in the pack before. The vines can be climbed. Web lines sit on vines because you chain them by clicking a line's block, and the vines are the blocks with outlines big enough to click. Pressing a button only flips its `powered` state, which shows the same model, so nothing visible changes.

**Corner webs** work like Human's and Mordor's beams (`FOUR_DIRECTIONS_COMPLEX`). Place one facing a wall to web that wall's corner with the ceiling, or with the floor for the floor item. Then shift+right-click the block from another side to web that side too, or to clear it. Where two neighbouring sides are both webbed, a web is spun across the inside corner as well. A block with no side webbed shows a small tuft, so it can still be found.

**The other webs** use `BLOCK`, which picks a random variant and turn, or `FOUR_DIRECTIONS`, where the model extends the way the builder faces.

Strands and sheets hang at most 2 blocks below the block they're placed in, because a model can't reach further. For a longer strand, click the bottom of the strand's block and place a *Strand Extension* under it, or use web lines.

## Inventory

`build.py` writes `inventory.yml`: the entries for RP-Inventories' `RP-PathsOfTheDead-Dev` branch, at the end of `inventories/det.yml`. They make two collections that link to each other. One is the webs, headed by *Web Strand (2 Tall)*. The other is the web lines, headed by *Web Line (45 degrees)*. The items are `CLAY_BALL` with custom model data 2518–2552.
