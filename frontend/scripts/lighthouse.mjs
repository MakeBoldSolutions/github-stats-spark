import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import lighthouse from "lighthouse";
import { preview } from "vite";
import { Launcher } from "chrome-launcher";
import puppeteer from "puppeteer-core";

const root = fileURLToPath(new URL("../", import.meta.url));
const reportDir = path.join(root, ".lighthouse");
const config = JSON.parse(
  await fs.readFile(path.join(root, ".lighthouserc.json"), "utf8"),
);
const executablePath =
  process.env.CHROME_PATH || Launcher.getInstallations()[0];
if (!executablePath)
  throw new Error("Chrome not found. Install Chrome or set CHROME_PATH.");
const server = await preview({
  root,
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
});
let browser;
try {
  // Own the browser lifecycle: Lighthouse's temporary-profile cleanup can fail on Windows.
  browser = await puppeteer.launch({ executablePath, headless: true });
  await fs.mkdir(reportDir, { recursive: true });
  const results = [];
  for (let run = 0; run < config.ci.collect.numberOfRuns; run++) {
    const result = await lighthouse("http://127.0.0.1:4173/", {
      port: Number(new URL(browser.wsEndpoint()).port),
      output: ["html", "json"],
      logLevel: "error",
      ...config.ci.collect.settings,
    });
    if (!result || result.lhr.runtimeError)
      throw new Error(JSON.stringify(result?.lhr.runtimeError));
    await fs.writeFile(
      path.join(reportDir, `run-${run + 1}.html`),
      result.report[0],
    );
    await fs.writeFile(
      path.join(reportDir, `run-${run + 1}.json`),
      result.report[1],
    );
    results.push(result.lhr);
  }
  const median = (values) =>
    [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
  const failures = [];
  for (const [id, assertion] of Object.entries(config.ci.assert.assertions)) {
    if (assertion === "off") continue;
    const [, limit] = assertion;
    let values;
    if (id.startsWith("categories:")) {
      values = results.map(
        (result) => result.categories[id.split(":")[1]]?.score,
      );
    } else if (id.startsWith("resource-summary:")) {
      const resource = id.split(":")[1];
      values = results.map(
        (result) =>
          result.audits["resource-summary"]?.details?.items?.find(
            (item) => item.resourceType === resource,
          )?.transferSize,
      );
    } else {
      values = results.map(
        (result) =>
          result.audits[id]?.[
            limit.maxNumericValue === undefined ? "score" : "numericValue"
          ],
      );
    }
    if (values.some((value) => value === undefined || value === null)) {
      failures.push(`${id}: audit unavailable`);
      continue;
    }
    const value = median(values);
    console.log(`${id}: ${value}`);
    if (limit.maxNumericValue !== undefined && value > limit.maxNumericValue)
      failures.push(`${id}: ${value} > ${limit.maxNumericValue}`);
    if (limit.minScore !== undefined && value < limit.minScore)
      failures.push(`${id}: ${value} < ${limit.minScore}`);
  }
  console.log(`Local reports: ${reportDir}`);
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exitCode = 1;
  }
} finally {
  await browser?.close();
  await new Promise((resolve, reject) =>
    server.httpServer.close((error) => (error ? reject(error) : resolve())),
  );
}
