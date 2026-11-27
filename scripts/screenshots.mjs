// README screenshots from the live site: node scripts/screenshots.mjs
// Set PW_CHANNEL=chrome to use an installed Google Chrome.
import { chromium } from "@playwright/test";

const base = process.env.BASE_URL ?? "https://quant-project-2.vercel.app";
const browser = await chromium.launch({
  channel: process.env.PW_CHANNEL || undefined,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
async function shot(name, { width, height }, tab, heading) {
  const page = await browser.newPage({ viewport: { width, height }, colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto(base);
  await page.getByTestId("fair-value").filter({ hasText: "₹" }).waitFor();
  if (tab) await page.getByRole("tab", { name: tab, exact: true }).click();
  await page.waitForLoadState("networkidle");
  if (heading) await page.getByRole("heading", { name: heading }).first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(5000); // let the 3D scenes draw
  await page.screenshot({ path: `docs/screenshots/${name}.jpg`, type: "jpeg", quality: 82 });
  await page.close();
}
const desktop = { width: 1400, height: 900 };
await shot("summary", desktop);
await shot("football-field", desktop, null, /Football field/);
await shot("sensitivity", { width: 1400, height: 1300 }, "Sensitivity", /^WACC × terminal growth$/);
await shot("monte-carlo", desktop, "Monte Carlo", /Distribution/);
await shot("phone", { width: 390, height: 844 });
await browser.close();
