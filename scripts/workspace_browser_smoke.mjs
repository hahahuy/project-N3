#!/usr/bin/env node

/*
 * Browser acceptance smoke for the real local Workspace.
 *
 * This script deliberately does not seed scenario data. It expects the API and
 * Vite app to be running and drives the data already served by the local
 * artifact root. Install Playwright in the calling environment before running:
 *
 *   node scripts/workspace_browser_smoke.mjs
 */

import process from "node:process";

const baseUrl = process.env.R2S_BROWSER_URL ?? "http://127.0.0.1:5173";

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (error) {
  console.error("workspace browser smoke requires the Playwright package");
  console.error("install it in the calling environment, then rerun this command");
  process.exitCode = 2;
}

if (chromium) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  try {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    const scenarioButtons = page.locator(".scenario-list button");
    const scenarioCount = await scenarioButtons.count();
    if (scenarioCount < 1) throw new Error("catalog did not return a scenario");
    await scenarioButtons.first().click();

    await page.getByRole("button", { name: "Recipe" }).click();
    await page.getByText("Named steps").waitFor();
    await page.getByRole("button", { name: "Variant studio" }).click();
    await page.getByRole("region", { name: "Variant studio" }).waitFor();

    if (scenarioCount >= 2) {
      await page.getByRole("button", { name: "compare" }).click();
      await page.getByRole("region", { name: "Compare mode" }).waitFor();
      await page.getByText(/synchronized on/).waitFor();
    }

    if (consoleErrors.length > 0) {
      throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
    }
    console.log(`workspace browser smoke: PASS (${scenarioCount} catalog scenarios)`);
  } finally {
    await browser.close();
  }
}
