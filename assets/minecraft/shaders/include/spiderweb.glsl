// Shelob's webs, and the slime in her lair. The webs - strands, sheets, the
// webs in corners and on floors, cocoons - are placed as the vines (weeping,
// twisting and cave vines, which have no collision and let one climb), their
// models planes of silk cut into pieces, and their textures painted with
// RP-PathOfTheDead's .tools/spiderwebs, which see. In these shaders:
//
// - they sway, slowly, in the lair's breath - gusts drifting through, the
//   same over a few blocks so that what's close sways together - each piece
//   of a web as far as it hangs from what holds it, which its texture holds
//   in each texel (below); and shiver while someone is among them. Moved in
//   the vertex shaders, the corners of their faces;
// - their silk is wet: slimed over here and there, sheened at a slant, beads
//   on it glinting where the view lines up with one, and slime creeping down
//   its strands. The sheen and glints catch the light, and up close a little
//   even in the dark (WEB_EYE_LIGHT), so that the webs show before one walks
//   into them;
// - the slime pools (block/spiderweb_slime_pool_*) are drawn over their
//   texture's shape as a fluid, as RP-Mordor's tar: slow, swirling, glossy,
//   bubbles swelling and bursting on it.
//
// They are told by their textures, as the fluids are (fluid.glsl): this
// pack's own kinds 6, the webs, and 7, the slime, which the sync signs
// (.mcme-shaders.json). Above the code, in bit 2 of a web texel's red, green
// and blue, how far it hangs from what holds it, 0 to 7 in half blocks (the
// tools' build.py writes it). No web texel is quite clear or quite opaque, so
// that all their faces go to the translucent pass alone and the code is
// compiled into no other (mcme_pass.glsl); their empty texels are all but
// clear (alpha 2), less than any pass keeps. Whatever draws without these
// shaders shows the webs as painted, still.
//
// Settings in spiderweb_config.glsl. Needs the base's fluid.glsl, imported
// before the hooks; the vertex shaders, which have no derivatives, define
// FLUID_VERTEX first.

#define FLUID_WEB 6
#define FLUID_SLIME 7

#ifdef FLUID_VERTEX
// ---------------------------------------------------------------- swaying

// How far the vertex at uv (its place in the atlas) hangs from what holds
// its web, 0 to 7 - or -1 if it isn't a web's. Its uv is a corner of its
// sprite, or within it: one of the four texels round it is the sprite's, as
// for the water's wind (waterWindHere). The faces that share a corner share
// its uv, so they find the same texel and move together.
int webReach(sampler2D atlas, vec2 uv) {
    ivec2 size = textureSize(atlas, 0);
    ivec2 corner = ivec2(round(uv * vec2(size)));
    for (int i = 0; i < 4; i++) {
        ivec2 t = clamp(corner - ivec2(i & 1, i >> 1), ivec2(0), size - 1);
        vec4 texel = texelFetch(atlas, t, 0);
        if (fluidIs(FLUID_WEB, atlas, texel, t)) {
            ivec3 c = ivec3(texel.rgb * 255.0 + 0.5);
            return ((c.r >> 2) & 1) | (((c.g >> 2) & 1) << 1) | (((c.b >> 2) & 1) << 2);
        }
    }
    return -1;
}

// How far to move the vertex at uv, pos from the camera, world its place
// (mod 64 blocks), time seconds: nothing, unless it's a web's - in the
// translucent pass, where they all are, and near enough to see it move.
vec3 webSway(sampler2D atlas, vec2 uv, vec3 pos, vec3 world, float time) {
#if defined(ALPHA_CUTOUT) && !defined(MCME_LITE)
    // (the translucent pass discards under 0.1, or Sodium's 0.01; cutout, 0.5)
    if (ALPHA_CUTOUT > 0.3 || dot(pos, pos) > WEB_SWAY_NEAR * WEB_SWAY_NEAR) return vec3(0.0);
    int level = webReach(atlas, uv);
    if (level <= 0) return vec3(0.0);
    float reach = float(level) / 7.0;
    // the gusts: broad, drifting, so that a web's faces, a block apart, sway
    // almost as one - and every breath, all of them a little more, then less
    vec2 q = world.xz;
    vec2 gust = fluidWarp(q - vec2(FLUID_STIR[3]) * FLUID_STEP * float(WEB_DRIFT) * time, vec2(0.125), 0.0, 960) * 2.0;
    float breath = sin(6.2831853 * (time / WEB_BREATH + fluidNoise(q, vec2(0.0625), 0.0, 961)));
    vec3 move = vec3(gust.x, 0.0, gust.y) * (0.65 + 0.35 * breath) * WEB_SWAY * reach;
    move.y = (breath * 0.5 + 0.5) * WEB_LIFT * reach;
    // the shiver: quick, small, only close by - what holds the web shivers
    // too, a little
    float near = 1.0 - smoothstep(WEB_SHIVER_NEAR * 0.25, WEB_SHIVER_NEAR, length(pos));
    if (near > 0.0) {
        float ph = 6.2831853 * fluidNoise(q, vec2(0.5), 0.0, 962);
        move += vec3(sin(time * 29.0 + ph), 0.7 * sin(time * 23.0 + ph * 1.7), sin(time * 31.0 + ph * 2.3))
              * WEB_SHIVER * near * (0.35 + 0.65 * reach);
    }
    return move;
#else
    return vec3(0.0);
#endif
}
#endif

#ifndef FLUID_VERTEX
// ---------------------------------------------------------------- the silk

// A web's colour, from color - its texture's, lit and shaded as any block's
// - where it is (f), its atlas coordinate and the atlas' size in texels, time
// seconds into the day, light the light it's lit by.
vec4 webLook(vec4 color, FluidFrame f, vec2 uv, vec2 atlasSize, float time, vec3 light) {
    // the texels left empty: gone in every pass
    if (color.a < 0.03) return vec4(color.rgb, 0.0);
    vec3 n = fluidNormal(f);
    float dist = length(f.pos);
    vec3 view = -f.pos / max(dist, 1.0e-4);
    float pixel = max(length(f.dx), length(f.dy));
    vec3 rgb = color.rgb;

    // slimed over in patches, fixed in the world
    float slimy = smoothstep(0.55, 0.8, fluidNoise(f.world.xz + f.world.y * 0.7, vec2(0.25), pixel, 963));
    rgb = mix(rgb, rgb * WEB_SLIME_TINT, slimy * WEB_SLIME);

    // what its wetness catches: the light, and up close a little more
    vec3 shine = light + vec3(WEB_EYE_LIGHT * (1.0 - smoothstep(0.0, WEB_EYE_REACH, dist)));

    // a sheen at a slant
    float slant = 1.0 - abs(dot(n, view));
    rgb += shine * WEB_SHEEN * slant * slant * slant * color.a * (0.6 + 0.4 * slimy);

    // beads glinting: some texels have one, each catching the light from its
    // own way, so that as the view moves, now this one, now that one flashes
    ivec2 t = ivec2(floor(uv * atlasSize));
    uint h = fluidHash(ivec4(t, 0, 964));
    if (color.a > 0.5 && float(h & 0xFFFFu) / 65535.0 < WEB_GLINTS) {
        vec3 way = normalize(vec3(float((h >> 16) & 255u), float((h >> 24) & 255u), float(fluidHash(ivec4(t, 1, 964)) & 255u)) / 127.5 - 1.0 + 1.0e-3);
        float glint = smoothstep(WEB_GLINT_SHARP, 1.0, abs(dot(view, way)));
        rgb += shine * glint * WEB_GLINT;
    }

    // slime creeping down the strands: where the texture runs downwards, a
    // bead in some of its columns, a texel's worth, now and then, a fainter
    // trail behind it
    vec3 flow = fluidFlow(f);
    float down = -flow.y / max(length(flow), 1.0e-6);
    if (down > 0.6 && color.a > 0.4) {
        vec2 tc = uv * atlasSize;
        uint hc = fluidHash(ivec4(int(floor(tc.x)), 0, 0, 965));
        if (float(hc & 0xFFFFu) / 65535.0 < WEB_DRIPS) {
            float at = mod(time * WEB_DRIP_SPEED + float(hc >> 16) / 65535.0 * WEB_DRIP_PERIOD, WEB_DRIP_PERIOD);
            float behind = mod(at - floor(mod(tc.y, WEB_DRIP_PERIOD)), WEB_DRIP_PERIOD);
            float bead = behind < 1.0 ? 1.0 : behind < 4.0 ? 0.35 * (4.0 - behind) / 3.0 : 0.0;
            rgb = mix(rgb, WEB_DRIP_COLOR * (light + shine * 0.6), bead * 0.85);
        }
    }
    return vec4(rgb, color.a);
}

// ---------------------------------------------------------------- the slime

// A bubble at q (blocks), time seconds into the day: swelling slowly into a
// glossy dome, then bursting. Its gloss.
float slimeBubble(vec2 q, float time) {
    const float spacing = 0.5;
    ivec2 cell = ivec2(floor(q / spacing));
    ivec2 id = cell & 127;
    float period = 6.0 + 2.0 * floor(fluidRand(ivec4(id, 0, 973)) * 4.0);  // 6 to 12: each divides 1200
    float t = time / period + fluidRand(ivec4(id, 1, 973));
    int rise = int(floor(t));
    if (fluidRand(ivec4(id, rise & 255, 974)) > SLIME_BUBBLES) return 0.0;
    float life = fract(t);
    vec2 at = (vec2(cell) + 0.3 + 0.4 * vec2(fluidRand(ivec4(id, rise & 255, 975)), fluidRand(ivec4(id, rise & 255, 976)))) * spacing;
    float r = spacing * 0.22 * pow(min(life / 0.85, 1.0), 0.6);
    float d = length(q - at);
    if (life < 0.85) {
        float dome = 1.0 - step(r, d);
        float shine = 1.0 - step(r * 0.4, length(q - at + vec2(0.35, 0.35) * r));
        return dome * (0.25 + shine * 0.75);
    }
    float burst = (life - 0.85) / 0.15;
    return (1.0 - step(SLIME_PIXEL, abs(d - r * (1.0 + 2.0 * burst)))) * (1.0 - burst) * 0.5;
}

// The slime's colour at f, time seconds into the day, lit the light it's lit
// by, color its texture's - whose shape it keeps.
vec4 slimeLook(vec4 color, FluidFrame f, float time, vec3 lit, vec3 light) {
    if (color.a < 0.3) return vec4(color.rgb, 0.0);
    vec3 n = fluidNormal(f);
    bool top = abs(n.y) > 0.6;
    vec3 axisU = top ? vec3(1.0, 0.0, 0.0) : abs(n.x) > abs(n.z) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
    vec3 axisV = top ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec2 s = vec2(dot(f.world, axisU), dot(f.world, axisV));
    vec2 here = (floor(s / SLIME_PIXEL) + 0.5) * SLIME_PIXEL;
    float pixel = max(max(length(f.dx), length(f.dy)), SLIME_PIXEL);

    // slow swirls, creeping
    vec2 q = here + fluidWarp(here - vec2(FLUID_STIR[1]) * FLUID_STEP * float(SLIME_CHURN) * time, vec2(0.5), pixel, 970) * 1.5;
    float swirl = fluidNoise(q, vec2(1.0), pixel, 971) * 0.65 + fluidNoise(q + 13.0, vec2(4.0), pixel, 972) * 0.35;
    float ridge = 1.0 - abs(2.0 * swirl - 1.0);
    vec3 rgb = SLIME_COLOR * (1.0 + (swirl - 0.5) * 2.0 * SLIME_SWIRL) * lit;
    float gloss = smoothstep(0.9, 0.99, ridge) * SLIME_GLOSS + slimeBubble(here, time) * SLIME_GLOSS;
    vec3 shine = light + vec3(WEB_EYE_LIGHT * (1.0 - smoothstep(0.0, WEB_EYE_REACH, length(f.pos))));
    rgb += shine * gloss * vec3(0.92, 0.96, 0.78);
    return vec4(rgb, SLIME_ALPHA * smoothstep(0.3, 0.6, color.a));
}
#endif
