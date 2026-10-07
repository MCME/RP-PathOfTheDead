// The fog block - a tripwire state with no collision, so it can be walked
// through (tripwire[attached=false,disarmed=false,powered=false,north=true,
// east=true,south=true,west=true]), block/fog - drawn on
// its faces as how much fog the view passes through inside it: from where
// the view ray enters the block to where it leaves it, the fog along the way
// summed from drifting, slowly changing wisps, thinner towards its top. So it
// is soft at its edges, where the view only grazes it, and blocks of it side
// by side and stacked add up into one fog, every face of each drawn (its
// model has no cull faces). It drifts from the west, and thins out round the
// camera, so that one can walk in it. Lit by the light alone - no shading of
// its faces, which would show them - and tinted with the sky's colour.
// Pixelated as a 16px texture is (FOG_PIXEL); its settings are in
// fog_block_config.glsl.
//
// RP-Mordor's fog block, from ResourcePackScripts' toolbox (prototypes/fog) -
// not its textured mist (mcme:block/mist): the same fog, made rarer, thinner
// and green by its settings alone. It is this pack's own fluid - the shader
// base keeps kinds 5 to 7 for a pack's own - told by block/fog, which the
// sync signs as kind 5 (.mcme-shaders.json), and drawn in
// mcme_hook_fragment_main.glsl. Needs the base's fluid.glsl, imported before
// the hooks.

#define FLUID_FOG 5
#define FOG_BLOCK FLUID_FOG

// Smooth value noise in three dimensions, on a lattice of cells per block,
// repeating every 64 blocks along each axis, as the world's coordinates here
// do - RP-Mordor's fluidNoise3, under the fog's own name, so that it can't
// clash with one the base may get.
float fogNoise3(vec3 p, float cells, int salt) {
    vec3 g = p * cells;
    ivec3 c = ivec3(floor(g));
    vec3 f = fract(g);
    f = f * f * (3.0 - 2.0 * f);
    int period = int(64.0 * cells + 0.5);
    ivec3 c0 = c - period * ivec3(floor(vec3(c) / float(period)));
    float n = 0.0;
    for (int k = 0; k < 8; k++) {
        ivec3 o = ivec3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
        ivec3 at = c0 + o - period * ivec3(greaterThanEqual(c0 + o, ivec3(period)));
        vec3 w = mix(1.0 - f, f, vec3(o));
        n += w.x * w.y * w.z * fluidRand(ivec4(at, salt));
    }
    return n;
}

// How thick the fog is at p (blocks), time seconds into the day; local its
// place in its block.
float fogDensity(vec3 p, vec3 local, float time) {
    // east and a little south, the finer wisps slower and turning against it
    vec3 wind = vec3(ivec3(FOG_DRIFT, 0, FOG_DRIFT / 3)) * FLUID_STEP * time;
    vec3 wind2 = vec3(ivec3(FOG_DRIFT / 2, 0, -FOG_CHURN)) * FLUID_STEP * time;
    float n = fogNoise3(p - wind, 1.0 / FOG_WISP, 800) * 0.65 + fogNoise3(p - wind2, 2.0 / FOG_WISP, 810) * 0.35;
    float wisps = smoothstep(FOG_PATCHY - 0.15, FOG_PATCHY + 0.25, n);
    return wisps * (1.0 - FOG_SETTLE * local.y) * FOG_DENSITY;
}

// The fog's colour - over the light - and opacity at f, time seconds into
// the day; sky the sky's colour.
vec4 fogLook(FluidFrame f, float time, vec3 sky) {
    vec3 n = fluidNormal(f);
    bool top = abs(n.y) > 0.6;
    vec3 axisU = top ? vec3(1.0, 0.0, 0.0) : abs(n.x) > abs(n.z) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
    vec3 axisV = top ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);

    // pixelated: the face is cut into squares of FOG_PIXEL blocks, each
    // traced once, through its middle
    vec2 s = vec2(dot(f.world, axisU), dot(f.world, axisV));
    vec2 snap = (floor(s / FOG_PIXEL) + 0.5) * FOG_PIXEL - s;
    vec3 shift = axisU * snap.x + axisV * snap.y;
    vec3 entry = f.world + shift;
    vec3 ray = normalize(f.pos + shift);

    // the block it enters - behind the face - and how far the ray goes in it
    vec3 cell = floor(entry - n * 0.001);
    vec3 local = clamp(entry - cell, 0.0, 1.0);
    vec3 exits = vec3(ray.x > 0.0 ? (1.0 - local.x) / ray.x : ray.x < 0.0 ? -local.x / ray.x : 1.0e9,
                      ray.y > 0.0 ? (1.0 - local.y) / ray.y : ray.y < 0.0 ? -local.y / ray.y : 1.0e9,
                      ray.z > 0.0 ? (1.0 - local.z) / ray.z : ray.z < 0.0 ? -local.z / ray.z : 1.0e9);
    float length_ = min(exits.x, min(exits.y, exits.z));

    // the fog along it, a few looks spread over the way
    float depth = 0.0;
    for (int i = 0; i < FOG_SAMPLES; i++) {
        float t = (float(i) + 0.5) / float(FOG_SAMPLES) * length_;
        depth += fogDensity(entry + ray * t, clamp(local + ray * t, 0.0, 1.0), time);
    }
    depth *= length_ / float(FOG_SAMPLES);
    float alpha = (1.0 - exp(-depth)) * FOG_MOST;
    // thinning out round the camera
    alpha *= smoothstep(FOG_CLEAR * 0.3, FOG_CLEAR, length(f.pos));
    return vec4(mix(FOG_COLOR, sky, FOG_TINT), alpha);
}
