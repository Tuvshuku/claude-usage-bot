// Optional development dependency: playwright. No dependencies ship with the site.
// Serve docs on localhost:8765, then run this script. Pass --capture for media.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const root = fileURLToPath(new URL("../", import.meta.url));
const base = process.env.SITE_URL || "http://127.0.0.1:8765";
const output = resolve(root, "docs/images");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_EXECUTABLE,
});
const errors = [];
try {
  const context = await browser.newContext({
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400)
      errors.push(`${response.status()} ${response.url()}`);
  });
  for (const width of [375, 820, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    await page.goto(base);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `overflow at ${width}px`,
    );
    const pet = page.locator("#demo-pet");
    assert.equal(await pet.getAttribute("aria-expanded"), "false");
    await pet.focus();
    await page.keyboard.press("Enter");
    assert.equal(await pet.getAttribute("aria-expanded"), "true");
    assert.equal(await page.locator("#demo-dashboard").isVisible(), true);
    await page.locator("[data-scene=hot]").click();
    assert.equal(await page.locator("#session-percent").textContent(), "94%");
    assert.equal(await page.locator("#demo").getAttribute("data-mood"), "hot");
    await page.locator("[data-scene=sleep]").click();
    assert.equal(await page.locator("#demo-status").textContent(), "idle");
    assert.equal(
      await page.locator("[data-scene=sleep]").getAttribute("aria-pressed"),
      "true",
    );
    await pet.click();
    assert.equal(await page.locator("#demo-dashboard").isVisible(), false);
    await page.locator("summary").first().click();
    assert.equal(
      await page.locator("details").first().getAttribute("open"),
      "",
    );
  }
  await page.locator("#copy-command").click();
  assert.equal(
    await page.evaluate(() => navigator.clipboard.readText()),
    "git clone https://github.com/Tuvshuku/claude-usage-bot.git\ncd claude-usage-bot\n./install.sh --service --autostart",
  );
  await page.evaluate(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
    }),
  );
  await page.locator("#copy-command").click();
  assert.match(
    await page.locator("#copy-status").textContent(),
    /copy them manually/,
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page
      .locator("#demo-pet svg")
      .evaluate((node) => getComputedStyle(node).animationName),
    "none",
  );
  for (const link of await page
    .locator('a[href^="#"]')
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href")))) {
    if (link !== "#")
      assert.equal(
        await page.locator(link).count(),
        1,
        `missing anchor ${link}`,
      );
  }
  assert.deepEqual(errors, [], "browser errors");
  console.log(
    "PASS: responsive layout, keyboard controls, moods, clipboard/fallback, reduced motion, anchors, browser errors",
  );
  if (process.argv.includes("--capture")) {
    await mkdir(output, { recursive: true });
    await page.setViewportSize({ width: 1280, height: 640 });
    await page.goto(`${base}/?press`);
    await page.locator("#demo-pet").click();
    await page.screenshot({ path: resolve(output, "launch-card.png") });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(base);
    await page.locator("#demo-pet").click();
    await page.screenshot({
      path: resolve(output, "landing-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base);
    await page.locator("#demo-pet").click();
    await page.screenshot({
      path: resolve(output, "landing-mobile.png"),
      fullPage: true,
    });
    const videoContext = await browser.newContext({
      viewport: { width: 1280, height: 640 },
      recordVideo: {
        dir: resolve(root, "build/site-video"),
        size: { width: 1280, height: 640 },
      },
    });
    const videoPage = await videoContext.newPage();
    await videoPage.goto(`${base}/?press`);
    await videoPage.waitForTimeout(2000);
    await videoPage.locator("#demo-pet").click();
    await videoPage.waitForTimeout(4000);
    await videoPage.locator("[data-scene=hot]").click();
    await videoPage.waitForTimeout(4000);
    await videoPage.locator("[data-scene=sleep]").click();
    await videoPage.waitForTimeout(3000);
    await videoPage.locator("[data-scene=happy]").click();
    await videoPage.waitForTimeout(2000);
    await videoContext.close();
    await videoPage.video().saveAs(resolve(output, "launch-demo.webm"));
    console.log(
      "Saved share card, desktop/mobile previews, and 15-second interactive-preview video.",
    );
  }
  await context.close();
} finally {
  await browser.close();
}
