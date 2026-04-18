# Video Reference: Diver Prompt Examples

## ltx2-19b-fast — Detailed Dive Scene

```
A professional scuba diver descending into deep ocean blue, rays of sunlight filtering through the water surface above, casting volumetric god rays that illuminate suspended particles in the water column. The diver wears a black wetsuit with neon green accents, fins kicking in slow rhythmic motion. Bubbles rise steadily upward from the regulator. Surrounding coral reef teems with colorful tropical fish—clownfish, angelfish, and a large school of silver barracuda circling in the background. Sea turtles glide majestically overhead. Camera follows the diver from behind, then slowly orbits to a front-facing shot as they approach a vibrant coral formation. Shot on Blackmagic Cinema Camera, underwater housing, 4K 60fps, natural light, cinematic color grading with rich blues and warm coral accents.
```

## Tips for High-Quality Diver Prompts

- **Camera movement**: Specify "camera follows", "orbiting shot", "static wide shot", "dolly shot"
- **Lighting**: "god rays", "backlit", "volumetric light", "sunlight filtering through surface"
- **Environment**: "coral reef", "kelp forest", "deep ocean", "shipwreck", "ice diving"
- **Marine life**: Name specific species for realism — "clownfish", "sea turtle", "barracuda school"
- **Technical specs**: Frame rate, resolution, camera type improve output consistency
- **Color grading**: Reference real cameras or LUT styles ("Arri Alexa look", "DJI cinema color")

## Per-Model Notes

- `ltx2-19b-fast` — Good for 3-5s clips, 768x512 default
- `wan22-t2v-lightning` — Supports up to 1280x720, 81 frames @ 16fps
- `hunyuan-video-t2v` — Strong for complex underwater physics, bubbles, caustics
- `ltx2-19b-dev` — Higher quality but slower
