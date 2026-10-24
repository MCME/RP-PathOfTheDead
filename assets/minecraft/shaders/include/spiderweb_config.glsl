// The webs' and the slime's settings (spiderweb.glsl). See spiderweb.glsl for
// what they are.

// ---- how they move (the vertex shaders)
// the lair's breath: slow gusts drifting through the webs, from the south-west,
// in whole steps of 64 blocks a day, so that they're back where they started
// when the day's clock starts over
#define WEB_SWAY 0.1                 // how far a web sways, at most, in blocks: where it hangs furthest (3.5 blocks or more) from what holds it
#define WEB_LIFT 0.03                // ...and rises and falls with each breath, in blocks
#define WEB_DRIFT 6                  // how fast the gusts drift (0.32 blocks a second)
#define WEB_BREATH 7.5               // a breath, in seconds: it divides the day's 1200
#define WEB_SWAY_NEAR 48.0           // webs further off than this, in blocks, hang still
// ...and shiver while someone is among them
#define WEB_SHIVER 0.022             // how far, at most, in blocks
#define WEB_SHIVER_NEAR 3.0          // within this of the camera, in blocks, the closer the more

// ---- how they look (the fragment shaders)
#define WEB_SLIME 0.55               // how much of the silk is slimed over, 0 to 1...
#define WEB_SLIME_TINT vec3(0.9, 0.98, 0.66)   // ...and its colour there, times the silk's
// (sheen, glints and drips only brighten the silk's own lit colour, by these shares: none gives light)
#define WEB_SHEEN 0.25               // its wet sheen, seen at a slant
#define WEB_GLINTS 0.08              // the share of its texels with a bead on them, which glints where the view lines up with it...
#define WEB_GLINT 0.35               // ...how much brighter it is then...
#define WEB_GLINT_SHARP 0.985        // ...and how seldom: the nearer 1, the fewer at once and the briefer
// slime sliding slowly down the strands, where their texture runs downwards
#define WEB_DRIPS 0.2                // the share of the texture's columns slime runs down
#define WEB_DRIP_SPEED 1.0           // in texels a second (1/16 block): 1200 x this, over WEB_DRIP_PERIOD, a whole number
#define WEB_DRIP_PERIOD 24.0         // how far apart the beads come down a column, in texels
#define WEB_DRIP_TINT vec3(0.7, 0.76, 0.48)    // the slime: the silk's colour, darkened and yellowed by this...
#define WEB_DRIP_GLOSS 0.15          // ...and each bead a little brighter than its trail

// ---- the slime's pools
#define SLIME_PIXEL (1.0 / 16.0)     // its pixels' size, in blocks, as the webs' 16px textures'
#define SLIME_COLOR vec3(0.44, 0.47, 0.3)      // a sickly, yellowed grey-green
#define SLIME_SWIRL 0.55             // how much its slow swirls lighten and darken it
#define SLIME_CHURN 2                // how fast they creep, in whole steps of 64 blocks a day
#define SLIME_GLOSS 0.75             // the gloss along the ridges of its swirls
#define SLIME_BUBBLES 0.35           // the share of its cells with a bubble swelling
#define SLIME_ALPHA 0.9              // how much it hides of what's under it
