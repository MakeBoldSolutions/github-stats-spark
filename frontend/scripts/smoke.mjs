import assert from "node:assert/strict";
import { preview } from "vite";
import { Launcher } from "chrome-launcher";
import puppeteer from "puppeteer-core";

const executablePath =
  process.env.CHROME_PATH || Launcher.getInstallations()[0];
if (!executablePath)
  throw new Error("Install Chrome or set CHROME_PATH for browser validation.");
const server = await preview({
  preview: { host: "127.0.0.1", port: 4175, strictPort: true },
});
let browser;
try {
  browser = await puppeteer.launch({ executablePath, headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://127.0.0.1:4175/", { waitUntil: "networkidle0" });
  await page.waitForSelector("article[role=button]");
  const title = await page.$eval(
    "article[role=button] a",
    (element) => element.textContent,
  );
  const search = "input[aria-label='Search repositories']";
  await page.type(search, title);
  await page.waitForFunction(
    () => document.querySelectorAll("article[role=button]").length === 1,
  );
  await page.locator(search).fill("");
  await page.waitForSelector("article[role=button]");
  await page.focus("article[role=button]");
  await page.keyboard.press("Enter");
  await page.waitForSelector("button[aria-label='Close']");
  await page.click("button[aria-label='Close']");
  await page.click("button[aria-label^='Insights']");
  await page.waitForSelector("canvas");
  await page.click("button[aria-label^='Health']");
  await page.waitForSelector("#attention-heading");
  await page.click("button[aria-label='Switch to repository overview']");
  await page.waitForSelector(search);
  await page.setViewport({ width: 375, height: 667 });
  const themeButton = "button[aria-label*='Switch to light mode']";
  await page.click(themeButton);
  assert.equal(
    await page.$eval("html", (element) => element.dataset.theme),
    "light",
  );
  assert.deepEqual(errors, [], "Browser reported uncaught JavaScript errors");
  console.log(
    "Browser smoke passed: data, search, details, charts, health, mobile, theme.",
  );
} finally {
  await browser?.close();
  await new Promise((resolve, reject) =>
    server.httpServer.close((error) => (error ? reject(error) : resolve())),
  );
}
