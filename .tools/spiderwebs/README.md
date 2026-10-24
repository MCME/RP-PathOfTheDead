# Shelob's webs

Spider webs for Shelob's lair: free-hanging strands, hanging sheets, corner and floor webs, cocoons, egg sacs and slime pools. Their shaders make them sway, shiver when someone is close, glint, and drip slime (`assets/minecraft/shaders/include/spiderweb.glsl`).

This folder starts with a dot, so it never goes into a zip.

## Workflow

```
python .tools/spiderwebs/paint.py              # only once: placeholder art for any texture that's missing
python .tools/spiderwebs/build.py              # models, blockstates, items, icons, inventory.yml; encodes textures
python <ResourcePackScripts>/generateVanilla/syncShaderBase.py .   # signs the textures, writes the 26.3 copies
```

Run `build.py`, then the sync, after **any** edit of a `textures/block/spiderweb_*.png`. A new texture also needs an entry in `.mcme-shaders.json`'s `fluids`: kind `6` for a web, `7` for slime.

Paint freely over the placeholder art. The textures are 32 texels per block, like RP-Mordor's webs. `build.py` handles the rest:

- **Alpha** is clamped to 2–253. Empty texels at alpha 2 stay invisible in every pass, and the web code compiles into the translucent pass only.
- **Bit 2 of red, green and blue** holds how far each texel hangs from its anchor, which drives the sway. Each texture's pattern comes from `WEIGHTS`, by name prefix: `hang`, held at the top; `sag_`, held at both ends; `fan_`, held at its top and right edges; and so on.

## Blocks

| Block | States | What |
|---|---|---|
| `weeping_vines` | age 0–19 | Strands (20–25 free) |
| `twisting_vines` | age 0–16 | Sheets (17–25 free) |
| `cave_vines` | age 0–25, berries=false | Corners and floors (berries=true would glow: shown, never placed) |
| `cave_vines_plant` / `weeping_vines_plant` / `twisting_vines_plant` | — | Cocoon / egg sacs / slime pool |

None of these blocks has collision, all of them can be climbed, and none was used in the pack before. Placement uses Architect's existing types: `BLOCK`, which picks a random variant and turn, and `FOUR_DIRECTIONS`, where the model extends the way the builder faces. Directional webs extend away from the builder. Corner webs go on the wall in front, or into the front-left corner.

Strands and sheets hang at most 2 blocks below the block they're placed in, because a model can't reach further. For a longer strand, click the bottom of the strand's block and place a *Strand Extension* under it.

## Inventory

`build.py` writes `inventory.yml`: the entries for RP-Inventories' `RP-PathsOfTheDead-Dev` branch, `inventories/det.yml`. They make one collection headed by *Web Strand (2 Tall)*. The items are `CLAY_BALL` with custom model data 2518–2547.
