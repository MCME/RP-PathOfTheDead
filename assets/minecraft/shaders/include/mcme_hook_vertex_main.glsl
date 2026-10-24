// Hook: a pack's own code in the terrain vertex shader's main(), right after
// objmc_main.glsl and before gl_Position is set from Pos. objmc's locals
// (atlasSize, isCustom, ...) and UV0, Position and texCoord are in scope.
//
// A pack overrides this file; this empty one is the shader base's. See
// mcme_hook_vertex_globals.glsl and docs/shader-base.md.

// RP-PathOfTheDead: the webs, swaying in the lair's breath and shivering
// while someone is among them (spiderweb.glsl)
if (isCustom == 0) {
    Pos += webSway(Sampler0, UV0, Pos, MCME_WORLD_POS_64, MCME_SECONDS);
}
