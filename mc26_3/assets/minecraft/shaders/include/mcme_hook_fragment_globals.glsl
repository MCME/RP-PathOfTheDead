// 26.3's copy of assets/minecraft/shaders/include/mcme_hook_fragment_globals.glsl, translated by ResourcePackScripts' shader_base.py: don't edit it.
#ifndef MCME_MCME_HOOK_FRAGMENT_GLOBALS_GLSL
#define MCME_MCME_HOOK_FRAGMENT_GLOBALS_GLSL
// RP-PathOfTheDead's own terrain features, hooked into the shader base's
// terrain fragment shaders - vanilla's and Sodium's (ResourcePackScripts/
// shaderBase, docs/shader-base.md). The base's fluid.glsl, which the fog
// block builds on, is imported.

// the fog blocks and clouds, traced from the eye (mcme_hook_vertex_globals.glsl)
layout(location = 21) flat in vec3 fogEye;
layout(location = 22) in vec4 fogLight;
#include <minecraft:fog_block_config.glsl>
#include <minecraft:fog_block.glsl>
// the ghost blocks' shimmer: clearer patches churning through them, built on
// the fog's noise - the fading ones' the others', widened
#include <minecraft:stone_shimmer.glsl>
#include <minecraft:ghost_shimmer.glsl>
#endif
