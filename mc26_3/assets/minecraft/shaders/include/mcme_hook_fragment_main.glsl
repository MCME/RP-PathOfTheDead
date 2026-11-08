// 26.3's copy of assets/minecraft/shaders/include/mcme_hook_fragment_main.glsl, translated by ResourcePackScripts' shader_base.py: don't edit it.
#ifndef MCME_MCME_HOOK_FRAGMENT_MAIN_GLSL
#define MCME_MCME_HOOK_FRAGMENT_MAIN_GLSL
// The base has told which fluid the face is (fluid) and where on it
// (fluidHere), and drawn its water.
// the fog blocks and clouds: the fog the view passes through behind the face,
// lit by the light alone - no shading of its faces, which would show them -
// and as if under the open sky, as much as FOG_OPEN says
if (fluid == FOG_BLOCK) {
    vec4 fog = fogLook(fluidHere, fogEye, Sampler0, MCME_TEXCOORD, MCME_SECONDS, MCME_FOG_COLOR.rgb);
    color = vec4(fog.rgb * mix(lightColor.rgb, fogLight.rgb, FOG_OPEN), fog.a);
}
// the texture's derivatives, for the ghost blocks' glow (stone_screen.glsl) -
// taken here, before branching, as they must be
vec2 stoneScreenDu = dFdx(MCME_TEXCOORD);
vec2 stoneScreenDv = dFdy(MCME_TEXCOORD);
// the fading ghost blocks: their textures, lit as any block's, but clearer
// along thin strips that rise and split, and glowing (ghost_screen.glsl)
if (fluid == GHOST_SHIMMER && MCME_PASS_HAS(GHOST_SHIMMER)) {
    float shimmer = ghostScreenShimmer(fluidHere, MCME_SECONDS);
    color.rgb = ghostScreenGlow(color.rgb, Sampler0, MCME_TEXCOORD, stoneScreenDu, stoneScreenDv, shimmer);
    color.a *= shimmer;
}
// ...and the other ghost blocks: churning fire, growing with distance and
// glowing where it is opaque (stone_screen.glsl)
if (fluid == STONE_SHIMMER && MCME_PASS_HAS(STONE_SHIMMER)) {
    float shimmer = stoneScreenShimmer(fluidHere, MCME_SECONDS);
    color.rgb = stoneScreenGlow(color.rgb, Sampler0, MCME_TEXCOORD, stoneScreenDu, stoneScreenDv, shimmer);
    color.a *= shimmer;
}
// ...kept down to 1% opacity, as Sodium keeps every translucent face: vanilla
// drops translucent terrain under 10% (its translucent_terrain pipeline's
// ALPHA_CUTOUT), which would cut this thin fog's soft edges away, face by
// face, into hard-edged blocks. Every other face keeps the pass's own.
#if defined(ALPHA_CUTOUT) && !defined(MCME_SODIUM)
float mcmeCutout = ALPHA_CUTOUT;
#undef ALPHA_CUTOUT
#define ALPHA_CUTOUT (fluid == FOG_BLOCK ? 0.01 : mcmeCutout)
#endif
#endif
