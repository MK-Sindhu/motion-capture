/**
 * Browser tests (e2e/): the built site, in Chrome, with a fake webcam that
 * shows MediaPipe's sample picture of two hands. Make the videos first:
 *
 *   python -m tests.web_e2e_media website/e2e/media   (from the repo root)
 *   npm run build && npm run test:e2e
 *
 * E2E_BROWSER_CHANNEL=chrome uses the installed Google Chrome instead of
 * Playwright's own Chromium (npx playwright install chromium).
 */

import { resolve } from "node:path";

import { defineConfig, devices } from "@playwright/test";

const media = resolve(process.env.E2E_MEDIA_DIR ?? "e2e/media");
const port = 4173;

export default defineConfig({
  testDir: "e2e",
  // Loading MediaPipe and tracking on the processor can be slow on CI machines
  timeout: 120_000,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://localhost:${port}`,
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    launchOptions: {
      args: [
        // Allow the camera without asking, and use a video file as the camera
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        `--use-file-for-fake-video-capture=${resolve(media, "hands.y4m")}`,
      ],
    },
  },
  webServer: {
    command: `npm run preview -- --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
  },
});
