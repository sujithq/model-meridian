import assert from "node:assert/strict";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const extensionDirectory = dirname(fileURLToPath(import.meta.url));
const packageMetadata = JSON.parse(
  await readFile(join(extensionDirectory, "package.json"), "utf8"),
);

assert.equal(packageMetadata.main, "./extension.mjs");

const registrations = [];
globalThis.__copilotCanvasTest = { registrations };

const testDirectory = await mkdtemp(join(tmpdir(), "model-meridian-canvas-"));
const sdkDirectory = join(
  testDirectory,
  "node_modules",
  "@github",
  "copilot-sdk",
);

try {
  await mkdir(sdkDirectory, { recursive: true });
  await Promise.all([
    copyFile(
      join(extensionDirectory, packageMetadata.main),
      join(testDirectory, "extension.mjs"),
    ),
    writeFile(
      join(sdkDirectory, "package.json"),
      JSON.stringify({
        name: "@github/copilot-sdk",
        type: "module",
        exports: { "./extension": "./extension.mjs" },
      }),
    ),
    writeFile(
      join(sdkDirectory, "extension.mjs"),
      `
        export function createCanvas(options) {
          return options;
        }

        export async function joinSession(configuration) {
          globalThis.__copilotCanvasTest.registrations.push(configuration);
          return {};
        }
      `,
    ),
  ]);

  await import(pathToFileURL(join(testDirectory, "extension.mjs")).href);

  assert.equal(registrations.length, 1);
  assert.equal(registrations[0].canvases.length, 1);

  const [canvas] = registrations[0].canvases;
  assert.deepEqual(
    {
      id: canvas.id,
      displayName: canvas.displayName,
      description: canvas.description,
    },
    {
      id: "model-meridian",
      displayName: "Model Meridian",
      description: "Explore AI model intelligence and cost data.",
    },
  );

  assert.deepEqual(await canvas.open({ instanceId: "test-instance" }), {
    title: "Model Meridian",
    status: "Connected to model-meridian.quintelier.dev",
    url: "https://model-meridian.quintelier.dev/",
  });
} finally {
  delete globalThis.__copilotCanvasTest;
  await rm(testDirectory, { recursive: true, force: true });
}

console.log("Model Meridian canvas registration verified.");
