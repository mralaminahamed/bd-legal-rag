import { test, expect } from "@playwright/test";
import { setupCommonMocks } from "./mocks";

test.describe("ActsPage", () => {
  test.beforeEach(async ({ page }) => {
    await setupCommonMocks(page);
    await page.route(/\/api\/v1\/admin\/acts\/labour-act-2006\/ingest/, (route) =>
      route.fulfill({
        json: { task_ids: ["task-1", "task-2"], message: "dispatched 2 tasks for act 'labour-act-2006'" },
      })
    );
  });

  test("loads and shows act name", async ({ page }) => {
    await page.goto("/acts");
    await expect(page.getByText("Labour Act 2006")).toBeVisible({ timeout: 10_000 });
  });

  test("shows ingestion run status", async ({ page }) => {
    await page.goto("/acts");
    await expect(page.getByText("succeeded")).toBeVisible({ timeout: 10_000 });
  });

  test("search filters acts list", async ({ page }) => {
    await page.goto("/acts");
    await page.getByPlaceholder("Search acts…").fill("Labour");
    await expect(page.getByText("Labour Act 2006")).toBeVisible();
  });

  test("clicking act row expands details", async ({ page }) => {
    await page.goto("/acts");
    await page.getByText("Labour Act 2006").click();
    await expect(page.getByText("Bengali (BN)")).toBeVisible({ timeout: 5_000 });
  });

  test("ingest button triggers toast", async ({ page }) => {
    await page.goto("/acts");
    // Use exact:true to avoid matching "Ingest all" — the per-row button has label "Ingest" only
    const ingestBtn = page.getByRole("button", { name: "Ingest", exact: true }).first();
    await ingestBtn.click();
    // onSuccess from triggerIngestAct: "Triggered 2 tasks for Labour Act 2006"
    await expect(
      page.getByText(/triggered \d+ tasks for labour act 2006/i)
    ).toBeVisible({ timeout: 8_000 });
  });
});
