# motion-capture website

The browser version of motion-capture, ready to deploy on Vercel. It has the
same two programs as the Python command:

- **Practice with a reference**: your webcam next to the teacher's video.
  Every frame, each of your hands is compared with the same hand in the
  reference and drawn green (close) or red (far off), with the difference in
  degrees. This is `motion-capture veena`.
- **Check hand tracking**: webcam only, with skeletons, fingertip trails, a
  bend bar per finger, and how often each hand is found. This is
  `motion-capture hand-check`.

MediaPipe runs inside the visitor's browser (WebAssembly, using the graphics
card when it can). The camera picture and the videos never leave the device.
The site is static files only: there is no server code and nothing is stored.
For now it shows **live results only**: there's no score screen or summary at
the end.

## Run it locally

Needs Node.js 22.12 or newer.

```bash
cd website
npm install
npm run dev          # http://localhost:5173 (the camera works on localhost)
```

`npm run dev` and `npm run build` first run `npm run assets`, which:

- copies MediaPipe's WebAssembly from `node_modules` into `public/mediapipe/`;
- downloads the hand model into `public/models/` (about 8 MB, once) and checks
  its SHA-256.

The site then serves both itself, so it doesn't depend on another website
while someone is using it.

## Deploy on Vercel

1. In Vercel: **Add New → Project**, then import the GitHub repo
   `MK-Sindhu/motion-capture`.
2. Set **Root Directory** to `website`.
3. Leave the rest. [`vercel.json`](vercel.json) sets the framework (Vite), the
   install and build commands, the output folder (`dist`), caching, and
   security headers.
4. Click **Deploy**. Vercel serves the site over https, which browsers require
   before they allow the camera.

Every push to `main` then redeploys automatically.

## Settings in the link

The settings form starts from the defaults, and the page link can change them.
The option names are the Python command's flags:

```
https://your-site.vercel.app/?threshold=25&countdown=5#veena
https://your-site.vercel.app/?trail-length=20#hand-check
```

| Option               | Meaning                                           | Default  |
| -------------------- | ------------------------------------------------- | -------- |
| `threshold`          | Degrees of difference below which a hand is green | 20       |
| `countdown`          | Seconds after the thumbs up before comparing      | 3        |
| `start-frames`       | Frames in a row the thumbs up must be seen        | 3        |
| `reference-mirrored` | The reference is a mirrored (selfie) video        | false    |
| `trail-length`       | Fingertip trail length in frames (hand check)     | 10       |
| `max-bend`           | Bend in degrees that fills a bar (hand check)     | 120      |
| `resolution`         | Webcam size to ask for, e.g. `1280x720`           | 1280x720 |

The camera is chosen on the page and remembered in that browser, so a nearby
iPhone can't take over.

## Same logic as the Python package

`src/` has the same layout as `src/motion_capture/`. Each module says which
Python module it matches:

```
src/
  apps/        handCheck.ts, veenaMatch.ts: the two programs, step for step
  config/      settings (same defaults and checks) and reading the page link
  geometry/    landmark numbers, joint angles
  tracking/    MediaPipe (handTracker.ts is the only file that loads it), left/right
  gestures/    thumbs up
  session/     waiting -> countdown -> running
  scoring/     comparing hands, the report
  rendering/   canvas drawing (same colours, sizes and positions as OpenCV)
  video/       webcam, video files, frames
  compat/      numpy-style sums and Python-style number formatting
  ui/          the page
```

**How "the same" is checked:** the Python package writes
[`tests/fixtures/parity-cases.json`](tests/fixtures/parity-cases.json) with
`python -m tests.parity_cases`, run from the repo root. The file holds fixed
inputs (synthetic hands, scripted sessions with thumbs-ups, countdowns,
Space/Esc and missing hands) and the outputs the Python code produced. The
website's tests ([`tests/parity.test.ts`](tests/parity.test.ts)) run the same
inputs through the TypeScript code. Numbers must agree to 1e-9 (in practice
about 13 decimal places), and the report text must match character for
character. A Python test fails if the file goes stale, so changing the logic
on one side without the other fails CI.

**What is deliberately different:**

- **The hand tracker.** The browser uses MediaPipe's current hand model; the
  Python package needs the older `mp.solutions` one. Their 3D estimates of the
  same hand differ by a few degrees, so scores aren't comparable between the
  two versions. Within one version you and the reference are measured by the
  same model. The browser model also labels left and right the other way
  round, so `tracking/detections.ts` swaps the labels back. This was measured
  on MediaPipe's sample pictures.
- **Reference playback.** The reference plays in real time, with optional
  sound. The Python version shows one reference frame per webcam frame, so it
  slows down when the computer does.
- **Live only.** There's no score screen at the end. The session summary goes
  to the browser's developer console.

## Checks

```bash
npm run check        # lint, formatting, types, unit + parity tests
npm run build        # production build into dist/

# Browser tests: the built site in Chrome with a fake webcam
(cd .. && python -m tests.web_e2e_media website/e2e/media)   # once: test videos
npm run test:e2e     # E2E_BROWSER_CHANNEL=chrome to use your installed Chrome
```

CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs all of
these on every push.
