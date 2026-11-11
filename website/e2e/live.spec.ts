/**
 * The real site, end to end: MediaPipe loads in the browser, the fake webcam
 * (MediaPipe's sample picture of two hands) is tracked live, and the programs
 * behave as in the Python version.
 *
 * The page shows live results only; at the end of a session the programs also
 * write their summary to the browser console, which these tests read.
 */

import { resolve } from "node:path";

import { expect, type Page, test } from "@playwright/test";

const media = resolve(process.env.E2E_MEDIA_DIR ?? "e2e/media");

/** Everything the page writes to the console, and any page errors. */
function watch(page: Page): { logs: string[]; errors: string[] } {
  const seen = { logs: [] as string[], errors: [] as string[] };
  page.on("console", (message) => seen.logs.push(message.text()));
  page.on("pageerror", (error) => seen.errors.push(error.message));
  return seen;
}

function trackedPct(summary: string, side: "Left" | "Right"): number {
  const match = new RegExp(`${side} hand \\(\\w+\\) tracked in (\\d+)% of frames`).exec(summary);
  return Number(match?.[1]);
}

test("hand check: both hands are tracked live", async ({ page }, testInfo) => {
  const seen = watch(page);
  await page.goto("/#hand-check");
  await expect(page.getByRole("tab", { name: "Check hand tracking" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const status = page.locator("#status");
  await expect(status).toContainText("Tracking live", { timeout: 90_000 });
  await expect(page.locator("#view")).toBeVisible();

  await page.waitForTimeout(4000);
  await page.locator("#view").screenshot({ path: testInfo.outputPath("hand-check.png") });
  await page.keyboard.press("Escape");
  await expect(status).toContainText("Stopped", { timeout: 15_000 });

  const summary = seen.logs.find((line) => line.includes("frames in"));
  expect(summary, "the hand-check summary in the console").toBeDefined();
  expect(trackedPct(summary as string, "Left")).toBeGreaterThanOrEqual(80);
  expect(trackedPct(summary as string, "Right")).toBeGreaterThanOrEqual(80);
  expect(seen.errors).toEqual([]);
  // The camera is switched off again
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();
});

test("veena practice: the same hands on both sides match closely", async ({ page }, testInfo) => {
  const seen = watch(page);
  // countdown=0 in the link: settings from the link work like the Python flags
  await page.goto("/?countdown=0#veena");
  await expect(page.locator("#opt-countdown")).toHaveValue("0");

  await page.locator("#reference-file").setInputFiles(resolve(media, "hands.webm"));
  await expect(page.locator("#reference-name")).toHaveText("hands.webm");
  await page.getByRole("button", { name: "Start", exact: true }).click();

  const status = page.locator("#status");
  await expect(status).toContainText("thumbs up", { timeout: 90_000 });
  await page.waitForTimeout(1500);
  await page.locator("#view").screenshot({ path: testInfo.outputPath("veena-waiting.png") });

  // The page's button presses Space, like the keyboard
  await page.getByRole("button", { name: /Start comparing now/ }).click();
  await expect(status).toContainText("Comparing live", { timeout: 15_000 });
  await page.waitForTimeout(4000);
  await page.locator("#view").screenshot({ path: testInfo.outputPath("veena-comparing.png") });
  await page.getByRole("button", { name: /^Stop/ }).click();
  await expect(status).toContainText("Stopped", { timeout: 15_000 });

  const report = seen.logs.find((line) => line.includes("Match Score"));
  expect(report, "the session report in the console").toBeDefined();
  expect(report).toContain("Left hand (fretting)");
  expect(report).toContain("Right hand (plucking)");
  const score = Number(/Match Score: ([\d.]+)%/.exec(report as string)?.[1]);
  expect(score).toBeGreaterThan(80);
  expect(seen.errors).toEqual([]);
});

test("a missing reference video is explained, not crashed on", async ({ page }) => {
  await page.goto("/#veena");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.locator("#status")).toHaveText("Choose the reference video first.");
  await expect(page.getByRole("button", { name: "Start", exact: true })).toBeEnabled();
});
