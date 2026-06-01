import { test, expect } from "@playwright/test";
import { setupCommonMocks } from "./mocks";

test.describe("DashboardPage", () => {
  test.beforeEach(async ({ page }) => {
    await setupCommonMocks(page);
  });

  test("loads and shows service status badge", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("online")).toBeVisible({ timeout: 10_000 });
  });

  test("shows total queries metric card", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Total queries (24h)")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("42")).toBeVisible();
  });

  test("shows recent query in table", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText("What is the weekly holiday entitlement?")
    ).toBeVisible({ timeout: 10_000 });
  });

  test("navigation sidebar has all 4 links", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Acts" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Playground" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
  });
});
