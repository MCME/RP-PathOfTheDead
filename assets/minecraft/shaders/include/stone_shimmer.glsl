// The ghost blocks' shimmer: every ghost block that doesn't fade - ghost
// bricks, small, mixed and weathered, smooth ghost stone, ghost cobblestone,
// the diamond pattern, the pillars, bars, chains, hooks, architraves and
// piles (the textures listed as kind 7 in .mcme-shaders.json), and the
// shimmering ghost stone (block/smooth_ghost_stone_shimmer): their textures,
// as they are, clearer where a pattern moves through them, as
// STONE_SHIMMER_STYLE says: a churning fire's dark patches, cold flames
// licking up each block, or patches drifting as the fog's wisps do
// (fog_block.glsl). The fading ghost blocks build on its fire, widening its
// patches (ghost_shimmer.glsl), so that the two kinds' patches run on into
// each other where they meet.
//
// Its patterns are smooth noise in the world - fogNoise3 - so that they run
// on from block to block and from face to face round an edge, and pixelated
// as a 16px texture is: each pixel of a face takes the pattern at its own
// middle, half a pixel into the block. They move in whole steps of 64 blocks
// a day (FLUID_STEP, 0.053 blocks a second), so that they are back where they
// started when the day's clock starts over.
//
// Its textures are this pack's own fluid of kind 7, so that the terrain
// shaders know them; their colour is the texture's, lit as any block's, and
// only their opacity is changed here, in mcme_hook_fragment_main.glsl. The
// bars', the chain's, the hook's, gray_stained_glass_half's and pink glass's
// clear texels are 1 in 255 opaque, not clear, as the fluids' code needs: the
// game drops them still. Whatever draws without these shaders - the Lite zip,
// a shader pack - shows the textures plain.

#define STONE_SHIMMER 7

// its settings
#define STONE_SHIMMER_STYLE 2        // 2: churning fire, 1: flames, 0: drifting patches
#define STONE_SHIMMER_CLEAR 0.55     // how much of its opacity the clearest pixels keep, 0 to 1
#define STONE_SHIMMER_STEPS 4.0      // how many steps of opacity a pixel goes through, as a pixel-art texture's (0: smooth)

// the churning fire: three layers of noise, each panning its own way at its
// own size, multiplied - so that their patches don't slide but swell, split
// and fade as the layers pass over each other - and looked up through a slow
// fourth that pushes them about, as realtimevfx's simple fire shader (the
// Diablo 3 technique) does. Its dark patches are where it is clear.
#define STONE_FIRE_SIZE 1.328125     // how fine it is: noise cells per block of its largest layer - 64 times it a whole number (85/64; 2.0 was 1.5x smaller)
#define STONE_FIRE_DARK 0.3          // below this (the layers' product, 1 on average) it is clearest...
#define STONE_FIRE_BRIGHT 0.95       // ...and above this as its texture is
#define STONE_FIRE_WARP 0.525        // how far the slow noise pushes the layers about, in blocks
#define STONE_FIRE_WARP_SIZE 0.671875 // ...and how fine that noise is, as STONE_FIRE_SIZE (43/64)
#define STONE_FIRE_SPEED 1           // how fast it all moves, a whole number: 1 as tuned, 2 twice as fast...

// the flames: tongues rising from each block's foot, each as tall as a noise
// along the block says, flickering, their tips bent and broken into wisps
#define STONE_FLAME_LOW 0.1          // how tall the shortest tongues are, as a share of the block
#define STONE_FLAME_HIGH 0.85        // ...and the tallest
#define STONE_FLAME_WIDTH 4.0        // how many tongues side by side, roughly, across a block (a power of two)
#define STONE_FLAME_WISPS 0.45       // how ragged their edges are
#define STONE_FLAME_SOFT 0.12        // how soft their edges are
#define STONE_FLAME_BEND 0.6         // how far their tips sway sideways, in blocks
#define STONE_FLAME_RISE 24          // how fast the wisps rise, in steps (an even number)
#define STONE_FLAME_FLICKER 16       // how fast the tongues grow and shrink, in steps

// the patches
#define STONE_SHIMMER_PATCHY 0.55    // how much of it stays as it is, between the patches, 0 to 1
#define STONE_SHIMMER_SOFT 0.2       // how soft a patch's edge is, as the noise goes
#define STONE_SHIMMER_SIZE 1.0       // how big the patches are, roughly, in blocks (a power of two)
#define STONE_SHIMMER_DRIFT 10       // how fast they drift, east and a little up, in steps
#define STONE_SHIMMER_CHURN 6        // how fast they change, the finer noise against them, in steps

// The churning fire's pattern itself at p, time seconds into the day: the
// three layers' product, 1 on average, low in its dark patches. The fading
// ghost blocks build on it too (ghost_shimmer.glsl), so that their blobs are
// these, widened, and run on into the other ghost blocks beside them.
float stoneFireField(vec3 p, float time) {
    float t = float(STONE_FIRE_SPEED) * FLUID_STEP * time;
    // the slow noise pushing the layers about, rising
    vec3 w = p - vec3(0.0, 6.0, 0.0) * t;
    vec3 q = p + (vec3(fogNoise3(w, STONE_FIRE_WARP_SIZE, 960), fogNoise3(w, STONE_FIRE_WARP_SIZE, 961), fogNoise3(w, STONE_FIRE_WARP_SIZE, 962)) - 0.5) * STONE_FIRE_WARP;
    // the three layers: up and a little south; up, east and north; west and south
    float a = fogNoise3(q - vec3(0.0, 10.0, 4.0) * t, STONE_FIRE_SIZE, 970) * 0.7
            + fogNoise3(q - vec3(0.0, 14.0, 4.0) * t, STONE_FIRE_SIZE * 2.0, 971) * 0.3;
    float b = fogNoise3(q - vec3(6.0, 8.0, -6.0) * t, STONE_FIRE_SIZE * 2.0, 972) * 0.7
            + fogNoise3(q - vec3(6.0, 12.0, -6.0) * t, STONE_FIRE_SIZE * 4.0, 973) * 0.3;
    float c = fogNoise3(q - vec3(-8.0, 4.0, 8.0) * t, STONE_FIRE_SIZE, 974);
    return a * b * c * 8.0;
}

// The churning fire at p, time seconds into the day: 0 where it is bright,
// to 1 in its darkest patches.
float stoneFire(vec3 p, float time) {
    return 1.0 - smoothstep(STONE_FIRE_DARK, STONE_FIRE_BRIGHT, stoneFireField(p, time));
}

// The flames at p, time seconds into the day: 0 where there are none, to 1.
float stoneFlame(vec3 p, float time) {
    float high = fract(p.y);
    vec3 rise = vec3(0.0, float(STONE_FLAME_RISE), 0.0) * FLUID_STEP * time;
    // along the face - x and z both, so that the flames run on round a corner -
    // swayed the more, the higher up
    float bend = (fogNoise3(p - rise * 0.5, 2.0, 920) - 0.5) * STONE_FLAME_BEND * high;
    float u = p.x + p.z + bend;
    // how tall the tongue here is, flickering: noise along the block's foot and in time
    float flicker = float(STONE_FLAME_FLICKER) * FLUID_STEP * time;
    float tall = fogNoise3(vec3(u * STONE_FLAME_WIDTH, floor(p.y) + 0.5, flicker), 1.0, 950);
    tall = clamp((tall - 0.5) * 2.2 + 0.5, 0.0, 1.0);
    // ...its edge broken by wisps rising through it
    float wisps = fogNoise3(vec3(u * 2.0, p.y, 0.0) - rise, 4.0, 930);
    float flame = mix(STONE_FLAME_LOW, STONE_FLAME_HIGH, tall) - high + (wisps - 0.5) * STONE_FLAME_WISPS;
    return smoothstep(0.0, STONE_FLAME_SOFT, flame);
}

// The patches at p, time seconds into the day: 0 where there are none, to 1.
float stonePatches(vec3 p, float time) {
    vec3 drift = vec3(ivec3(STONE_SHIMMER_DRIFT, 1, STONE_SHIMMER_DRIFT / 2)) * FLUID_STEP * time;
    vec3 churn = vec3(ivec3(-STONE_SHIMMER_CHURN, 0, STONE_SHIMMER_CHURN)) * FLUID_STEP * time;
    float noise = fogNoise3(p - drift, 1.0 / STONE_SHIMMER_SIZE, 900) * 0.65
                + fogNoise3(p - churn, 2.0 / STONE_SHIMMER_SIZE, 910) * 0.35;
    return smoothstep(STONE_SHIMMER_PATCHY, STONE_SHIMMER_PATCHY + STONE_SHIMMER_SOFT, noise);
}

// Where the face's pixel at f takes the pattern: its middle, half a pixel
// into the block.
vec3 stonePixel(FluidFrame f) {
    vec3 n = fluidNormal(f);
    bool top = abs(n.y) > 0.6;
    vec3 axisU = top ? vec3(1.0, 0.0, 0.0) : abs(n.x) > abs(n.z) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
    vec3 axisV = top ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec2 s = vec2(dot(f.world, axisU), dot(f.world, axisV));
    vec2 snap = (floor(s / FOG_PIXEL) + 0.5) * FOG_PIXEL - s;
    return f.world + axisU * snap.x + axisV * snap.y - n * (0.5 * FOG_PIXEL);
}

// How much of its opacity the face keeps at f, time seconds into the day:
// 1 where it is as its texture is, STONE_SHIMMER_CLEAR where it is clearest.
float stoneShimmer(FluidFrame f, float time) {
    vec3 p = stonePixel(f);

#if STONE_SHIMMER_STYLE == 2
    float clear = stoneFire(p, time);
#elif STONE_SHIMMER_STYLE == 1
    float clear = stoneFlame(p, time);
#else
    float clear = stonePatches(p, time);
#endif
    if (STONE_SHIMMER_STEPS > 0.0) clear = floor(clear * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
    return mix(1.0, STONE_SHIMMER_CLEAR, clear);
}
