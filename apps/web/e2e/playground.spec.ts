import { test, expect } from "@playwright/test";
import { setupCommonMocks } from "./mocks";

test.describe("PlaygroundPage", () => {
  test.beforeEach(async ({ page }) => {
    await setupCommonMocks(page);
    await page.route("**/api/v1/query/stream", (route) => {
      const body =
        'data: {"type":"token","text":"Section 103 ","answer":null,"citations":null,"disclaimer":null,"cached":false,"degraded":false,"declined":false}\n\n' +
        'data: {"type":"final","text":"","answer":"Section 103 provides for weekly holiday.\\n\\n---\\nFor information only.","citations":[],"disclaimer":"For information only.","cached":false,"degraded":false,"declined":false}\n\n';
      void route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body,
      });
    });
  });

  test("loads with question textarea", async ({ page }) => {
    await page.goto("/playground");
    await expect(
      page.getByPlaceholder(/Ask a legal question/i)
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows disclaimer after answer", async ({ page }) => {
    await page.goto("/playground");
    await page.getByPlaceholder(/Ask a legal question/i).fill(
      "What is the weekly holiday?"
    );
    await page.getByRole("button", { name: /^Ask$/i }).click();
    await expect(page.getByText("For information only.").first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("shows act filter dropdown with All Acts option", async ({ page }) => {
    await page.goto("/playground");
    // The act filter is a <select> — check the element contains the "All Acts" option
    const actSelect = page.locator("select").nth(1);
    await expect(actSelect).toBeVisible({ timeout: 10_000 });
    await expect(actSelect.locator("option[value='']")).toHaveText("All Acts");
  });

  test("shows Labour Act option in dropdown", async ({ page }) => {
    await page.goto("/playground");
    // Wait for the acts data to load, then verify the option exists in the select
    const actSelect = page.locator("select").nth(1);
    await expect(actSelect).toBeVisible({ timeout: 10_000 });
    await expect(
      actSelect.locator("option[value='labour-act-2006']")
    ).toHaveText("Labour Act 2006");
  });

  test("UI language toggle switches to Bengali", async ({ page }) => {
    await page.goto("/playground");
    await page.locator("select").first().selectOption("bn");
    await expect(
      page.getByPlaceholder(/বাংলা বা ইংরেজিতে/i)
    ).toBeVisible({ timeout: 5_000 });
  });
});
