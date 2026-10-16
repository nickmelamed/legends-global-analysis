import { expect, type Page, test } from "@playwright/test";
import { formatValue } from "../src/format";

async function apiOverview(page: Page, query: string) {
  const res = await page.request.get(`/api/overview?${query}`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

test("defaults show Summit last week with the API's attendance", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview/);
  await expect(page.getByTestId("window")).toContainText("SSD · Sep 28, 2026 – Oct 4, 2026");
  const api = await apiOverview(page, "venue=SSD&preset=last_week&compare=true&compare_mode=prior_period");
  const attendance = api.kpis.find((k: { key: string }) => k.key === "attendance").current;
  const shown = await page.getByTestId("tile-attendance").getByTestId("value").textContent();
  expect(shown).toBe(formatValue(attendance, "count"));
  await expect(page.getByTestId("trend-chart")).toBeVisible();
  await expect(page.getByTestId("freshness")).toContainText("Data last refreshed");
});

test("filters live in the URL, survive navigation and reset", async ({ page }) => {
  await page.goto("/overview");
  await page.getByLabel("Three Rivers Observatory").check();
  await page.getByLabel("Date range").selectOption("month_to_date");
  await page.getByLabel("Compare to").selectOption("last_year");
  await page.getByLabel("Compare on").uncheck();
  await expect(page).toHaveURL(/venue=TRO.*preset=month_to_date.*compare=false/);
  await page.getByRole("link", { name: "Ticketing" }).click();
  await expect(page).toHaveURL(/\/ticketing\?.*preset=month_to_date.*compare=false/);
  await expect(page.getByLabel("Three Rivers Observatory")).toBeChecked();
  await page.goBack();
  await expect(page).toHaveURL(/\/overview\?.*preset=month_to_date/);
  await expect(page.getByTestId("window")).toContainText("SSD, TRO");
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByLabel("Summit Sky Deck")).toBeChecked();
  await expect(page.getByLabel("Three Rivers Observatory")).not.toBeChecked();
  await expect(page.getByLabel("Date range")).toHaveValue("last_week");
  await expect(page.getByLabel("Compare on")).toBeChecked();
  await expect(page.getByLabel("Compare to")).toHaveValue("prior_period");
  await expect(page.getByTestId("window")).toContainText("SSD · Sep 28, 2026 – Oct 4, 2026");
});

test("a week with a missing feed day marks the gap, never a dip", async ({ page }) => {
  await page.goto("/overview?venue=RTL&preset=custom&start=2026-04-13&end=2026-04-19");
  await expect(page.getByTestId("data-gaps")).toContainText("RTL");
  await expect(page.getByTestId("tile-attendance")).toContainText("Missing feed days");
  await expect(page.getByTestId("pace-attendance")).toContainText("data gap, no status");
  await expect(page.getByTestId("dept-Ticket")).toContainText("Missing days");
  await expect(page.getByTestId("trend-chart")).toContainText("No data");
  await page.getByRole("button", { name: "Table" }).click();
  await expect(page.getByRole("row", { name: /Apr 18/ })).toContainText("No data");
});

test("a day with no feed shows No data, not zero", async ({ page }) => {
  await page.goto("/overview?venue=RTL&preset=custom&start=2026-04-18&end=2026-04-18");
  const value = page.getByTestId("tile-attendance").getByTestId("value");
  await expect(value).toHaveText("No data");
  await expect(page.getByTestId("tile-total_revenue").getByTestId("value")).toHaveText("No data");
});

test("custom with no dates asks for dates instead of erroring", async ({ page }) => {
  await page.goto("/overview");
  await page.getByLabel("Date range").selectOption("custom");
  await expect(page.getByTestId("pick-dates")).toBeVisible();
  await expect(page.getByTestId("error")).toHaveCount(0);
});

test("an out-of-scope venue shows the access message", async ({ page }) => {
  await page.setExtraHTTPHeaders({ "X-Dev-User": "marcus@dev" });
  await page.goto("/overview?venue=RTL");
  await expect(page.getByTestId("error")).toContainText("do not have access");
  await expect(page.getByTestId("freshness")).toContainText("do not have access");
});

test("the trend switches grain through the API", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByTestId("trend-chart")).toBeVisible();
  const request = page.waitForRequest(/\/api\/trend\?.*grain=week/);
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await request;
  await expect(page.getByRole("button", { name: "Week", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("trend-chart")).toBeVisible();
});

test("ticket filters tag only the ticket metrics", async ({ page }) => {
  await page.goto("/overview");
  await page.getByLabel("INDIVIDUAL").check();
  await expect(page.getByTestId("tile-attendance")).toContainText("Ticket filters applied");
  await expect(page.getByTestId("tile-ticket_revenue")).toContainText("Ticket filters applied");
  await expect(page.getByTestId("tile-total_revenue")).not.toContainText("Ticket filters applied");
  await expect(page.getByTestId("tile-payroll")).not.toContainText("Ticket filters applied");
});

test("the logo is the black file on light and the white file on dark", async ({ page }) => {
  await page.goto("/overview");
  const logo = page.getByRole("img", { name: "Legends Global" });
  await expect(logo).toHaveAttribute("src", /logo-horizontal-black\.png/);
  await page.getByRole("button", { name: "Toggle light and dark mode" }).click();
  await expect(logo).toHaveAttribute("src", /logo-horizontal-white\.png/);
});

test("the cutover note takes its date from the API", async ({ page }) => {
  await page.goto("/overview?preset=year_to_date&compare_mode=last_year");
  await expect(page.getByTestId("cutover")).toContainText("Feb 3, 2026");
  // A different date from the API must show, so the page cannot hardcode it.
  await page.route(/\/api\/overview\?/, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.window.cutover_date = "2025-07-15";
    await route.fulfill({ response: res, json: body });
  });
  await page.reload();
  await expect(page.getByTestId("cutover")).toContainText("Jul 15, 2025");
  await expect(page.getByTestId("cutover")).not.toContainText("Feb 3, 2026");
});

test("the phone drawer closes on Escape", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/overview");
  await expect(page.getByRole("link", { name: "Help & Support" })).toBeVisible();
  await page.getByRole("button", { name: "Open menu" }).click();
  const sidebar = page.getByRole("complementary", { name: "Navigation and filters" });
  await expect(sidebar).toHaveClass(/open/);
  await sidebar.getByRole("link", { name: "Overview" }).focus();
  await page.keyboard.press("Escape");
  await expect(sidebar).not.toHaveClass(/open/);
  await expect(page.getByRole("button", { name: "Open menu" })).toBeFocused();
});

for (const width of [390, 1440]) {
  for (const theme of ["light", "dark"]) {
    test(`layout ${width} ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.addInitScript((t) => localStorage.setItem("attractions-theme", t), theme);
      await page.goto("/overview");
      await expect(page.getByTestId("trend-chart")).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      const scroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(scroll).toBeLessThanOrEqual(0);
      // Writing the files is opt-in so a test run leaves the tree clean.
      if (process.env.SCREENSHOTS) {
        await page.screenshot({ path: `../docs/screenshots/overview-${width}-${theme}.png`, fullPage: true });
      }
    });
  }
}
