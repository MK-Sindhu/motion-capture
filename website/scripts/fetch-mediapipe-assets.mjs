// Puts MediaPipe's files where the site serves them from (public/):
//   - its WebAssembly program, copied from node_modules/@mediapipe/tasks-vision
//   - the hand model, downloaded once and checked against its SHA-256 checksum
//
// Runs before `npm run dev` and `npm run build`, so the site never depends on
// another website while someone is using it. Both folders are gitignored.

import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { copyFile, mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const assets = JSON.parse(await readFile(join(root, "src/tracking/mediapipe-assets.json"), "utf8"));

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

// ---- WebAssembly files ----
const wasmFrom = join(root, "node_modules/@mediapipe/tasks-vision/wasm");
const wasmTo = join(root, "public", assets.wasmDir);
await rm(wasmTo, { recursive: true, force: true });
await mkdir(wasmTo, { recursive: true });
// Only the variant the site loads (FilesetResolver.forVisionTasks without
// `useModule`); the "module" variant is the same program packaged differently.
for (const name of await readdir(wasmFrom)) {
  if (name.startsWith("vision_wasm_internal.")) {
    await copyFile(join(wasmFrom, name), join(wasmTo, name));
  }
}
console.log(`MediaPipe WebAssembly -> public/${assets.wasmDir}`);

// ---- hand model ----
const modelPath = join(root, "public", assets.model.path);
if (existsSync(modelPath) && sha256(await readFile(modelPath)) === assets.model.sha256) {
  console.log(`Hand model already in public/${assets.model.path}`);
} else {
  console.log(`Downloading the hand model from ${assets.model.url}`);
  const response = await fetch(assets.model.url);
  if (!response.ok) {
    throw new Error(`Hand model download failed: HTTP ${response.status}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  const actual = sha256(bytes);
  if (actual !== assets.model.sha256) {
    throw new Error(`Hand model checksum mismatch: expected ${assets.model.sha256}, got ${actual}`);
  }
  await mkdir(dirname(modelPath), { recursive: true });
  // Write to a temporary name first, so a half-written file is never used.
  await writeFile(`${modelPath}.part`, bytes);
  await rename(`${modelPath}.part`, modelPath);
  console.log(`Hand model -> public/${assets.model.path}`);
}
