// Every ghost block but the fading ones (pack fluid kind 7): stone_shimmer.glsl's
// churning fire, but its blobs growing in the world as it gets further away
// (STONE_SCREEN_GROWTH) - at 1, the same size on the screen at every
// distance, twice as far, twice as big - and glowing where it leaves them
// opaque (STONE_SCREEN_GLOW_). First tried on a test block, ghost_bricks_screen
// (sulfur_wall, all sides tall, up=false), which stoneScreenIs still tells
// apart by its 128px texture, though nothing needs to now.
//
// It is still fixed to the block, not to the screen: the fire is drawn at
// sizes a power of two apart, each fixed to the world, and blended from one to
// the next as the distance grows, as a texture's mipmaps are - so it neither
// slides over the block as the camera moves nor jumps from size to size.
//
// The noise repeats every 64 blocks; at each size it must too, so the fire's
// sizes here are ones that 64 blocks hold a whole number of, at every size up
// to STONE_SCREEN_MOST (as the other blocks' sizes are, at theirs).

#define STONE_SCREEN_TEXELS 128.0  // how many texels a block its texture shows, which marks it (every other ghost face: 60 or fewer)
#define STONE_SCREEN_DISTANCE 8.0    // how far away, in blocks, its blobs are the size they are on the fading ghost blocks
#define STONE_SCREEN_GROWTH 0.8     // how fast its blobs grow in the world with distance, as a power of it: 1 the same size on the screen at every distance, 0.5 half as fast (4x as far: 2x as big), 0 not at all, as the fading ghost blocks
#define STONE_SCREEN_NEAR 17.0     // nearer than this, in blocks, its blobs stay the size they are at this distance
#define STONE_SCREEN_FAR 85.0      // ...and further than this, the size they are at this distance
#define STONE_SCREEN_SLOW 0.65      // how fast it moves near you, as a share of STONE_FIRE_SPEED...
#define STONE_SCREEN_SLOW_DISTANCE 30.0 // ...up to this distance, in blocks
#define STONE_SCREEN_SLOW_BLEND 4.0  // how many blocks either side of it the two speeds blend over (each is fixed to the world, so blending, not switching, keeps the fire from jumping)
#define STONE_SCREEN_LEAST 3         // up to how many times smaller they get, close up, as a power of two (3: 8x)
#define STONE_SCREEN_MOST 4          // up to how many times bigger they get, far away, as a power of two (4: 16x)
#define STONE_SCREEN_CLEAR 0.45      // how much of its opacity the clearest pixels keep, 0 to 1
#define STONE_SCREEN_SIZE 1.75       // as STONE_FIRE_SIZE, at STONE_SCREEN_DISTANCE - 64 times it a whole number of times 2 to the STONE_SCREEN_MOST (112/64; 1.5 was 1.17x bigger)
#define STONE_SCREEN_WARP_SIZE 0.75  // as STONE_FIRE_WARP_SIZE, the same (48/64)
#define STONE_SCREEN_PIXELS false    // whether its pixels grow with it, far away, as its blobs do (false: always a 16px texture's)
#define STONE_SCREEN_GLOW_MOST 0.7   // how much its most opaque parts glow: how far towards STONE_SCREEN_GLOW_BRIGHT, whatever the light, 0 to 1
#define STONE_SCREEN_GLOW_LEAST 0.45 // ...and its clearest parts
#define STONE_SCREEN_GLOW_BRIGHT 1.1 // how bright the glow is: 1 its texture as in full daylight, more brighter still

// How many texels a block the face shows at uv: its texture's, as the atlas
// holds it, over the face's size - taken before branching, as it needs
// derivatives.
float stoneScreenTexels(sampler2D atlas, vec2 uv, FluidFrame f) {
    vec2 size = vec2(textureSize(atlas, 0));
    vec2 ux = dFdx(uv) * size;
    vec2 uy = dFdy(uv) * size;
    float face = length(cross(f.dx, f.dy));
    return face > 0.0 ? sqrt(abs(ux.x * uy.y - ux.y * uy.x) / face) : 0.0;
}

// Whether a face that fine is this texture's.
bool stoneScreenIs(float texels) {
    return texels > STONE_SCREEN_TEXELS * 0.75 && texels < STONE_SCREEN_TEXELS * 1.5;
}

// The fire's pattern at p, scale times as big in the world as at
// STONE_SCREEN_DISTANCE: stoneFireField's, every size, drift and warp scaled.
float stoneScreenField(vec3 p, float time, float scale, float speed) {
    float t = float(STONE_FIRE_SPEED) * speed * FLUID_STEP * time * scale;
    float size = STONE_SCREEN_SIZE / scale;
    float warp = STONE_SCREEN_WARP_SIZE / scale;
    vec3 w = p - vec3(0.0, 6.0, 0.0) * t;
    vec3 q = p + (vec3(fogNoise3(w, warp, 960), fogNoise3(w, warp, 961), fogNoise3(w, warp, 962)) - 0.5) * STONE_FIRE_WARP * scale;
    float a = fogNoise3(q - vec3(0.0, 10.0, 4.0) * t, size, 970) * 0.7
            + fogNoise3(q - vec3(0.0, 14.0, 4.0) * t, size * 2.0, 971) * 0.3;
    float b = fogNoise3(q - vec3(6.0, 8.0, -6.0) * t, size * 2.0, 972) * 0.7
            + fogNoise3(q - vec3(6.0, 12.0, -6.0) * t, size * 4.0, 973) * 0.3;
    float c = fogNoise3(q - vec3(-8.0, 4.0, 8.0) * t, size, 974);
    return a * b * c * 8.0;
}

// The middle of the fragment's pixel, pixel blocks big, on its face (as stonePixel).
vec3 stoneScreenPixel(FluidFrame f, float pixel) {
    vec3 n = fluidNormal(f);
    bool top = abs(n.y) > 0.6;
    vec3 axisU = top ? vec3(1.0, 0.0, 0.0) : abs(n.x) > abs(n.z) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
    vec3 axisV = top ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec2 s = vec2(dot(f.world, axisU), dot(f.world, axisV));
    vec2 snap = (floor(s / pixel) + 0.5) * pixel - s;
    return f.world + axisU * snap.x + axisV * snap.y - n * (0.5 * FOG_PIXEL);
}

// How clear the fire leaves it at one size and speed, 0 to 1.
float stoneScreenClear(FluidFrame f, float time, float scale, float speed) {
    float pixel = STONE_SCREEN_PIXELS ? FOG_PIXEL * max(scale, 1.0) : FOG_PIXEL;
    return 1.0 - smoothstep(STONE_FIRE_DARK, STONE_FIRE_BRIGHT, stoneScreenField(stoneScreenPixel(f, pixel), time, scale, speed));
}

// ...at the fragment's distance's sizes (far: as stoneScreenShimmer works it out), one speed.
float stoneScreenClearAt(FluidFrame f, float time, float far, float speed) {
    float size = min(floor(far), float(STONE_SCREEN_MOST - 1));
    return mix(stoneScreenClear(f, time, exp2(size), speed), stoneScreenClear(f, time, exp2(size + 1.0), speed), far - size);
}

float stoneScreenShimmer(FluidFrame f, float time) {
    float away = length(f.pos);
    float far = STONE_SCREEN_GROWTH * log2(clamp(away, STONE_SCREEN_NEAR, STONE_SCREEN_FAR) / STONE_SCREEN_DISTANCE);
    far = clamp(far, -float(STONE_SCREEN_LEAST), float(STONE_SCREEN_MOST));
    // near: STONE_SCREEN_SLOW's speed; far: full speed; between, the two blended
    float fast = smoothstep(STONE_SCREEN_SLOW_DISTANCE - STONE_SCREEN_SLOW_BLEND, STONE_SCREEN_SLOW_DISTANCE + STONE_SCREEN_SLOW_BLEND, away);
    float clear = fast >= 1.0 ? stoneScreenClearAt(f, time, far, 1.0)
                : fast <= 0.0 ? stoneScreenClearAt(f, time, far, STONE_SCREEN_SLOW)
                : mix(stoneScreenClearAt(f, time, far, STONE_SCREEN_SLOW), stoneScreenClearAt(f, time, far, 1.0), fast);
    if (STONE_SHIMMER_STEPS > 0.0) clear = floor(clear * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
    return mix(1.0, STONE_SCREEN_CLEAR, clear);
}

// Its colour, lit as any block's (lit), glowing where the fire leaves it
// opaque (shimmer: stoneScreenShimmer's, 1 opaque) and less where it leaves it
// clear: its texture, unlit, mixed in - read pixel-sharp, as the terrain
// shaders' sampleNearest reads it, with uv's derivatives (du, dv) taken before
// branching. (A plain texture() read of the atlas is filtered: blurry.)
vec3 stoneScreenGlow(vec3 lit, sampler2D atlas, vec2 uv, vec2 du, vec2 dv, float shimmer) {
    vec2 pixel = 1.0 / vec2(textureSize(atlas, 0));
    vec2 texels = uv / pixel;
    vec2 centre = round(texels) - 0.5;
    vec2 offset = clamp((texels - centre - 0.5) * pixel / max(sqrt(du * du + dv * dv), vec2(1e-9)) + 0.5, 0.0, 1.0);
    vec3 own = textureGrad(atlas, (centre + offset) * pixel, du, dv).rgb * STONE_SCREEN_GLOW_BRIGHT;
    float opaque = clamp((shimmer - STONE_SCREEN_CLEAR) / (1.0 - STONE_SCREEN_CLEAR), 0.0, 1.0);
    return mix(lit, max(lit, own), mix(STONE_SCREEN_GLOW_LEAST, STONE_SCREEN_GLOW_MOST, opaque));
}
