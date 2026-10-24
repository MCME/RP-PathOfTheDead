# Shelob's webs

Spider webs for Shelob's lair: free-hanging strands, hanging sheets, corner and floor webs, cocoons, egg sacs and slime pools. Their shaders make them sway, shiver when someone is close, glint, and drip slime (`assets/minecraft/shaders/include/spiderweb.glsl`).

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
- **Bit 2 of red, green and blue** holds how far each texel hangs from its anchor, which drives the sway. Each texture's pattern comes from `WEIGHTS`, by name prefix: `hang`, held at the top; `sag_`, held at both ends; `fan_`, held at its top and right edges; and so on.

## Blocks

| Block | States | What |
|---|---|---|
| `vine` | all 32 | Corner webs: each side webbed or not; `up=false` at the ceiling, `up=true` at the floor |
| `weeping_vines` | age 0–19 | Strands (20–25 free) |
| `twisting_vines` | age 0–16 | Sheets (17–25 free) |
| `cave_vines` | age 4–11, 20–25, berries=false | Large corner, wall corner, floors (0–3 and 12–19 free; berries=true would glow: shown, never placed) |
| `cave_vines_plant` / `weeping_vines_plant` / `twisting_vines_plant` | — | Cocoon / egg sacs / slime pool |

None of these blocks has collision, all of them can be climbed, and none was used in the pack before.

**Corner webs** work like Human's and Mordor's beams (`FOUR_DIRECTIONS_COMPLEX`). Place one facing a wall to web that wall's corner with the ceiling, or with the floor for the floor item. Then shift+right-click the block from another side to web that side too, or to clear it. Where two neighbouring sides are both webbed, a web is spun across the inside corner as well. A block with no side webbed shows a small tuft, so it can still be found.

**The other webs** use `BLOCK`, which picks a random variant and turn, or `FOUR_DIRECTIONS`, where the model extends the way the builder faces.

Strands and sheets hang at most 2 blocks below the block they're placed in, because a model can't reach further. For a longer strand, click the bottom of the strand's block and place a *Strand Extension* under it.

## Inventory

`build.py` writes `inventory.yml`: the entries for RP-Inventories' `RP-PathsOfTheDead-Dev` branch, `inventories/det.yml`. They make one collection headed by *Web Strand (2 Tall)*. The items are `CLAY_BALL` with custom model data 2518–2546.
