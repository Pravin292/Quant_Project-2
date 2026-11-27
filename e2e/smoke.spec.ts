import { expect, test } from "@playwright/test";

// F29: open the deployed app, move a slider, and check that the fair value changes.
test("moving a slider changes the fair value", async ({ page }) => {
  await page.goto("/");
  const fair = page.getByTestId("fair-value");
  await expect(fair).toContainText("₹", { timeout: 30_000 });
  const before = await fair.textContent();

  const slider = page.getByRole("slider", { name: "Year 1" });
  await slider.focus();
  for (let i = 0; i < 40; i++) await slider.press("ArrowRight");

  await expect(fair).not.toHaveText(before ?? "", { timeout: 30_000 });
});

test("every tab opens without an error message", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("fair-value")).toContainText("₹", { timeout: 30_000 });
  for (const name of ["Historical", "Forecast", "Valuation bridge", "Sensitivity", "Monte Carlo", "Peers", "Methodology", "Summary"]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.getByRole("tabpanel")).not.toBeEmpty();
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  }
});

test("a share link reproduces the valuation", async ({ page, context }) => {
  await page.goto("/");
  const fair = page.getByTestId("fair-value");
  await expect(fair).toContainText("₹", { timeout: 30_000 });
  const before = await fair.textContent();
  const slider = page.getByRole("slider", { name: "Year 1" });
  await slider.focus();
  for (let i = 0; i < 40; i++) await slider.press("ArrowRight");
  await expect(fair).not.toHaveText(before ?? "", { timeout: 30_000 });
  await expect(page).toHaveURL(/#s=/);
  await page.waitForLoadState("networkidle");
  const changed = await fair.textContent();

  const second = await context.newPage();
  await second.goto(page.url());
  await expect(second.getByTestId("fair-value")).toHaveText(changed ?? "", { timeout: 30_000 });
});
