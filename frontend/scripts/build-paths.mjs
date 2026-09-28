import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

export const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
export const outputDir = path.resolve(
  repositoryRoot,
  process.env.SPARK_BUILD_DIR || "docs",
);
const allowed = [
  path.join(repositoryRoot, "docs"),
  path.join(repositoryRoot, ".validation", "site"),
];
if (!allowed.includes(outputDir))
  throw new Error("SPARK_BUILD_DIR must be docs or .validation/site");

export function clean() {
  for (const directory of [
    outputDir,
    path.join(repositoryRoot, "frontend", "dist"),
    path.join(repositoryRoot, "frontend", ".vite"),
  ]) {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

export function copyData() {
  for (const name of ["data", "output"]) {
    const source = path.join(repositoryRoot, name);
    const destination = path.join(outputDir, name);
    if (!fs.existsSync(source)) continue;
    fs.rmSync(destination, { recursive: true, force: true });
    fs.mkdirSync(destination, { recursive: true });
    fs.cpSync(source, destination, { recursive: true });
  }
}
