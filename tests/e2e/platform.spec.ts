/**
 * End-to-end smoke suite (Playwright) — runs against the Docker Compose stack.
 *
 * Usage:
 *   npx playwright install chromium
 *   BASE_URL=http://localhost:3000 npx playwright test tests/e2e
 */
import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";

test("login page renders", async ({ page }) => {
  await page.goto(`${BASE_URL}/login`);
  await expect(page.getByText("Enterprise AI Platform")).toBeVisible();
});

test("admin can sign in and reach the dashboard", async ({ page }) => {
  await page.goto(`${BASE_URL}/login`);
  await page.getByPlaceholder("admin@example.com").fill(ADMIN_EMAIL);
  await page.getByPlaceholder("••••••••••").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Overview")).toBeVisible({ timeout: 10_000 });
});

test("navigation reaches every module", async ({ page }) => {
  await page.goto(`${BASE_URL}/login`);
  await page.getByPlaceholder("admin@example.com").fill(ADMIN_EMAIL);
  await page.getByPlaceholder("••••••••••").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  for (const item of ["RAG Studio", "Playground", "Agents", "Monitoring", "Governance"]) {
    await page.getByRole("link", { name: item }).click();
    await expect(page).toHaveURL(/dashboard|rag|playground|agents|monitoring|governance/);
  }
});
