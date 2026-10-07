// The fog block's settings (fog_block.glsl). See fog_block.glsl for what it is.
// Paths of the Dead's is much rarer, much thinner and greener than RP-Mordor's,
// whose values are noted where they differ.

#define FOG_PIXEL (1.0 / 16.0)       // its pixels' size, in blocks, as a 16px texture's

#define FOG_DENSITY 0.8              // how thick it is where it is thickest: per block of fog looked through (Mordor: 1.0)
#define FOG_MOST 0.5                 // the most it hides, 0 to 1, so the world always shows through it (0.8)
#define FOG_PATCHY 0.68              // how much of it is clear, between its wisps, 0 to 1 (0.55)
#define FOG_WISP 2.0                 // how big its wisps are, roughly, in blocks (a power of two)
#define FOG_SAMPLES 3                // how many times it is looked at, along the view through a block
#define FOG_SETTLE 0.4               // how much thinner it is at the top of a block than at its bottom, 0 to 1

// how it drifts: from the west, as the water's waves, in whole steps of 64
// blocks a day (0.053 blocks a second), so that it is back where it started
// when the day's clock starts over
#define FOG_DRIFT 6                  // its wisps (0.32 a second)
#define FOG_CHURN 2                  // how fast they change, against the drift

#define FOG_COLOR vec3(0.66, 0.8, 0.66)    // a pale green, as the Dead's ghost blocks (Mordor: vec3(0.8, 0.81, 0.82))
#define FOG_TINT 0.15                // how much it takes the sky's colour, 0 to 1
#define FOG_CLEAR 1.5                // it thins out round the camera within this, in blocks
