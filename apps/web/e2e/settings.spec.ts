import { test, expect } from "@playwright/test";
import { setupCommonMocks } from "./mocks";

test.describe("SettingsPage", () => {
  test.beforeEach(async ({ page }) => {
    await setupCommonMocks(page);
  });

  test("loads and shows service health section", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByText("Service health")).toBeVisible({ timeout: 10_000 });
  });

  test("shows admin bearer token card", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByText("Admin bearer token")).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.getByPlaceholder("Enter admin bearer token")
    ).toBeVisible();
  });

  test("shows current LLM config from mock", async ({ page }) => {
    await page.goto("/settings");
    // "anthropic" and "env" are rendered in <code> tags in the LLM override section
    await expect(page.getByRole("code").filter({ hasText: "anthropic" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("env").first()).toBeVisible();
  });

  test("set override button is present", async ({ page }) => {
    await page.goto("/settings");
    await expect(
      page.getByRole("button", { name: "Set override" })
    ).toBeVisible({ timeout: 10_000 });
  });
});
