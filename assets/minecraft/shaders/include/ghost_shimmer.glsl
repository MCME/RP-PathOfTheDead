// The fading ghost blocks - fading ghost bricks and stone, and the fading
// bars, architraves and pillars (the textures listed as kind 6 in
// .mcme-shaders.json): their textures, as they are, clearer where the other
// ghost blocks' churning fire (stone_shimmer.glsl) has its dark patches - the
// same patches, so that they run on from these blocks into the others beside
// them, but widened, the more where a slow, broad noise says, and clear in
// their cores. At a patch's rim it is as faint as the other blocks' patches,
// so that where the two kinds meet, a patch crossing between them shows only
// a little change. It took the place of the fading blocks' frame animation,
// which faded each block as one.
//
// Their textures are this pack's own fluid of kind 6, so that the terrain
// shaders know them; their colour is the texture's, lit as any block's, and
// only their opacity is changed here, in mcme_hook_fragment_main.glsl. The
// fading bars' clear texels are 1 in 255 opaque, not clear, as the fluids'
// code needs: the game drops them still. Whatever draws without these shaders
// - the Lite zip, a shader pack - shows the textures plain.
//
// It needs stone_shimmer.glsl, imported before it, and builds on its fire
// whatever STONE_SHIMMER_STYLE is: its size, speed and edges are the fire's
// there (STONE_FIRE_), and its rims' faintness STONE_SHIMMER_CLEAR.

#define GHOST_SHIMMER 6

// its settings
#define GHOST_SHIMMER_CLEAR 0.18     // how much of its opacity the clearest pixels keep, in its patches' cores, 0 to 1
#define GHOST_FADE_GROW 0.6          // how much wider its patches are than the other ghost blocks', as the fire's pattern goes
#define GHOST_FADE_LEAST 0.3         // ...at least, as a share of that, where the broad noise says least
#define GHOST_FADE_SIZE 0.328125     // how big the broad noise's spots are: noise cells per block - 64 times it a whole number (21/64; 0.5 was 1.5x smaller)
#define GHOST_FADE_CORE 0.35         // how much of the widening its clear cores keep: 0 cores as wide as the patches, 1 as the other blocks' patches
#define GHOST_FADE_DEEP 0.25         // how far inside a patch its core starts, as the fire's pattern goes

// How much of its opacity the face keeps at f, time seconds into the day:
// 1 where it is as its texture is, GHOST_SHIMMER_CLEAR where it is clearest.
float ghostShimmer(FluidFrame f, float time) {
    vec3 p = stonePixel(f);
    float fire = stoneFireField(p, time);
    // the broad noise saying where the patches are widened most, drifting
    // with the fire, up and a little east
    vec3 drift = vec3(2.0, 6.0, -2.0) * float(STONE_FIRE_SPEED) * FLUID_STEP * time;
    float broad = clamp((fogNoise3(p - drift, GHOST_FADE_SIZE, 990) - 0.5) * 2.2 + 0.5, 0.0, 1.0);
    float grow = GHOST_FADE_GROW * mix(GHOST_FADE_LEAST, 1.0, broad);
    // the patches, widened, as faint at their rims as the other blocks'...
    float rim = 1.0 - smoothstep(STONE_FIRE_DARK, STONE_FIRE_BRIGHT, fire - grow);
    // ...and their cores, clearer
    float core = 1.0 - smoothstep(STONE_FIRE_DARK, STONE_FIRE_BRIGHT, fire - grow * (1.0 - GHOST_FADE_CORE) + GHOST_FADE_DEEP);
    if (STONE_SHIMMER_STEPS > 0.0) {
        rim = floor(rim * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
        core = floor(core * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
    }
    return mix(1.0, STONE_SHIMMER_CLEAR, rim) * mix(1.0, GHOST_SHIMMER_CLEAR / STONE_SHIMMER_CLEAR, core);
}
