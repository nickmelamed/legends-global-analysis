import { expect, test } from "@playwright/test";

test("a recorded answer is shown with its checked figures", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Question").fill("How did last week compare to last year?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("answer")).toContainText("$84,328.25");
  await expect(page.getByTestId("check")).toHaveText("Checked against the data");
  const total = page.getByTestId("ask-table").getByRole("row", { name: /Total revenue/ });
  await expect(total).toContainText("$84,328.25");
  await expect(total).toContainText("$91,891.36");
  await expect(total).toContainText("vs Sep 29, 2025 – Oct 5, 2025");
  // Writing the file is opt-in so a test run leaves the tree clean.
  if (process.env.SCREENSHOTS) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: "../docs/screenshots/ask-1440-light.png", fullPage: true });
  }
});

test("an unanswerable question shows the numbers only", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Question").fill("Something nobody recorded?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("answer")).toHaveCount(0);
  await expect(page.getByTestId("check")).toContainText("Showing the numbers only");
  await expect(page.getByTestId("ask-table")).toContainText("Total revenue");
});

test("Ask the data is in the navigation and keeps the filters", async ({ page }) => {
  await page.goto("/overview?venue=TRO");
  await page.getByRole("link", { name: "Ask the data" }).click();
  await expect(page).toHaveURL(/\/ask\?venue=TRO/);
});
