// 26.3's copy of assets/minecraft/shaders/include/ghost_screen.glsl, translated by ResourcePackScripts' shader_base.py: don't edit it.
#ifndef MCME_GHOST_SCREEN_GLSL
#define MCME_GHOST_SCREEN_GLSL
// The fading ghost blocks (pack fluid kind 6): the other ghost blocks' blobs
// (stone_screen.glsl), unchanged - same pattern, size, speed and settings, so
// the two run on seamlessly where they meet - with a second layer of bigger,
// slower, clearer blobs cut through them as well: its own noise (other salts),
// so where its blobs are has nothing to do with where the first layer's are, at
// any distance.

#define GHOST_LAYER_SIZE 1.0         // as STONE_SCREEN_SIZE, for the second layer - less is bigger (1.0: 1.75x the first layer's 1.75; 64 times it a whole number of times 16)
#define GHOST_LAYER_SPEED 0.8        // how fast they move through the world against the first layer's, 0 to 1
#define GHOST_LAYER_DARK 0.45        // as STONE_FIRE_DARK: below this its blobs are clearest - more: wider blobs, and more of them
#define GHOST_LAYER_BRIGHT 1.1       // ...and above this they leave it as it is
#define GHOST_LAYER_KEEP 0.3         // how much of its opacity the second layer's clearest pixels keep, 0 to 1 - on top of the first layer's - up to GHOST_LAYER_KEEP_NEAR blocks away...
#define GHOST_LAYER_KEEP_FAR 0.75    // ...and from GHOST_LAYER_KEEP_FAR_AT blocks on (blended between), so far away it is gentler
#define GHOST_LAYER_KEEP_NEAR 16.0
#define GHOST_LAYER_KEEP_FAR_AT 64.0

// stoneScreenField, on other salts and at GHOST_LAYER_SIZE.
float ghostLayerField(vec3 p, float time, float scale, float speed) {
    float t = float(STONE_FIRE_SPEED) * speed * FLUID_STEP * time * scale;
    float size = GHOST_LAYER_SIZE / scale;
    float warp = STONE_SCREEN_WARP_SIZE / scale;
    vec3 w = p - vec3(0.0, 6.0, 0.0) * t;
    vec3 q = p + (vec3(fogNoise3(w, warp, 980), fogNoise3(w, warp, 981), fogNoise3(w, warp, 982)) - 0.5) * STONE_FIRE_WARP * scale;
    float a = fogNoise3(q - vec3(0.0, 10.0, 4.0) * t, size, 990) * 0.7
            + fogNoise3(q - vec3(0.0, 14.0, 4.0) * t, size * 2.0, 991) * 0.3;
    float b = fogNoise3(q - vec3(6.0, 8.0, -6.0) * t, size * 2.0, 992) * 0.7
            + fogNoise3(q - vec3(6.0, 12.0, -6.0) * t, size * 4.0, 993) * 0.3;
    float c = fogNoise3(q - vec3(-8.0, 4.0, 8.0) * t, size, 994);
    return a * b * c * 8.0;
}

// How clear the second layer leaves it at one size and speed, 0 to 1...
float ghostLayerClear(FluidFrame f, float time, float scale, float speed) {
    float pixel = STONE_SCREEN_PIXELS ? FOG_PIXEL * max(scale, 1.0) : FOG_PIXEL;
    return 1.0 - smoothstep(GHOST_LAYER_DARK, GHOST_LAYER_BRIGHT, ghostLayerField(stoneScreenPixel(f, pixel), time, scale, speed));
}

// ...at the fragment's distance's two sizes, blended (as stoneScreenClearAt).
float ghostLayerClearAt(FluidFrame f, float time, float far, float speed) {
    float size = min(floor(far), float(STONE_SCREEN_MOST - 1));
    return mix(ghostLayerClear(f, time, exp2(size), speed), ghostLayerClear(f, time, exp2(size + 1.0), speed), far - size);
}

// How much of its opacity the fragment keeps: 1 opaque - stoneScreenShimmer's
// blobs, times the second layer's.
float ghostScreenShimmer(FluidFrame f, float time) {
    float away = length(f.pos);
    float far = STONE_SCREEN_GROWTH * log2(clamp(away, STONE_SCREEN_NEAR, STONE_SCREEN_FAR) / STONE_SCREEN_DISTANCE);
    far = clamp(far, -float(STONE_SCREEN_LEAST), float(STONE_SCREEN_MOST));
    float fast = smoothstep(STONE_SCREEN_SLOW_DISTANCE - STONE_SCREEN_SLOW_BLEND, STONE_SCREEN_SLOW_DISTANCE + STONE_SCREEN_SLOW_BLEND, away);
    float slow = STONE_SCREEN_SLOW * GHOST_LAYER_SPEED;
    float first = fast >= 1.0 ? stoneScreenClearAt(f, time, far, 1.0)
                : fast <= 0.0 ? stoneScreenClearAt(f, time, far, STONE_SCREEN_SLOW)
                : mix(stoneScreenClearAt(f, time, far, STONE_SCREEN_SLOW), stoneScreenClearAt(f, time, far, 1.0), fast);
    float second = fast >= 1.0 ? ghostLayerClearAt(f, time, far, GHOST_LAYER_SPEED)
                 : fast <= 0.0 ? ghostLayerClearAt(f, time, far, slow)
                 : mix(ghostLayerClearAt(f, time, far, slow), ghostLayerClearAt(f, time, far, GHOST_LAYER_SPEED), fast);
    if (STONE_SHIMMER_STEPS > 0.0) {
        first = floor(first * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
        second = floor(second * STONE_SHIMMER_STEPS + 0.5) / STONE_SHIMMER_STEPS;
    }
    float keep = mix(GHOST_LAYER_KEEP, GHOST_LAYER_KEEP_FAR, smoothstep(GHOST_LAYER_KEEP_NEAR, GHOST_LAYER_KEEP_FAR_AT, away));
    return mix(1.0, STONE_SCREEN_CLEAR, first) * mix(1.0, keep, second);
}

// Its colour: as the other ghost blocks' (stoneScreenGlow), its glow going by
// the first layer alone, so the second's blobs are clear, not dark.
vec3 ghostScreenGlow(vec3 lit, sampler2D atlas, vec2 uv, vec2 du, vec2 dv, float shimmer) {
    return stoneScreenGlow(lit, atlas, uv, du, dv, max(shimmer, STONE_SCREEN_CLEAR));
}
#endif
