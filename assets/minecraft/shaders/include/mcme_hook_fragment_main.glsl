// The base has told which fluid the face is (fluid) and where on it
// (fluidHere), and drawn its water.
// the fog blocks and clouds: the fog the view passes through behind the face,
// lit by the light alone - no shading of its faces, which would show them -
// and as if under the open sky, as much as FOG_OPEN says
if (fluid == FOG_BLOCK) {
    vec4 fog = fogLook(fluidHere, fogEye, Sampler0, MCME_TEXCOORD, MCME_SECONDS, MCME_FOG_COLOR.rgb);
    color = vec4(fog.rgb * mix(lightColor.rgb, fogLight.rgb, FOG_OPEN), fog.a);
}
// the webs: wet silk, glinting, slime creeping down it; and the slime's pools
// (spiderweb.glsl) - lit and shaded as any block, their wetness catching the
// light
if (fluid == FLUID_WEB && MCME_PASS_HAS(FLUID_WEB)) {
    color = webLook(color, fluidHere, MCME_TEXCOORD, MCME_ATLAS_SIZE, MCME_SECONDS, lightColor.rgb);
}
if (fluid == FLUID_SLIME && MCME_PASS_HAS(FLUID_SLIME)) {
    color = slimeLook(color, fluidHere, MCME_SECONDS, vertexColor.rgb * lightColor.rgb, lightColor.rgb);
}
// ...kept down to 1% opacity, as Sodium keeps every translucent face: vanilla
// drops translucent terrain under 10% (its translucent_terrain pipeline's
// ALPHA_CUTOUT), which would cut this thin fog's soft edges away, face by
// face, into hard-edged blocks - and the film of silk between a web's cords.
// Every other face keeps the pass's own.
#if defined(ALPHA_CUTOUT) && !defined(MCME_SODIUM)
float mcmeCutout = ALPHA_CUTOUT;
#undef ALPHA_CUTOUT
#define ALPHA_CUTOUT (fluid == FOG_BLOCK || fluid == FLUID_WEB ? 0.01 : mcmeCutout)
#endif
