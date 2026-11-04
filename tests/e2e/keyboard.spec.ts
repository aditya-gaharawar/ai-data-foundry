import { test, expect, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let index = 0; index < 100; index++) {
    if (await target.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error("The requested control was not reachable with Tab.");
}

async function activate(page: Page, target: Locator) {
  await tabTo(page, target);
  await page.keyboard.press("Enter");
}

test("keyboard-only lifecycle from sign-in through JSONL export", async ({
  page,
}) => {
  const line = readFileSync(".env", "utf8")
    .split("\n")
    .find((value) => value.startsWith("DEV_PASSWORD="))!;
  const password = line.slice("DEV_PASSWORD=".length);
  await page.goto("/login");
  await tabTo(page, page.getByLabel("Email address", { exact: true }));
  await page.keyboard.type("alex@foundry.local");
  await tabTo(page, page.getByLabel("Password", { exact: true }));
  await page.keyboard.type(password);
  await activate(
    page,
    page.getByRole("button", { name: "Sign in", exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await activate(
    page,
    page.getByRole("button", { name: "Create dataset", exact: true }),
  );
  const dialog = page.getByRole("dialog");
  await tabTo(page, dialog.getByLabel("Dataset name", { exact: true }));
  const name = `Keyboard lifecycle ${Date.now()}`;
  await page.keyboard.type(name);
  await tabTo(page, dialog.getByRole("checkbox"));
  await page.keyboard.press("Space");
  await activate(
    page,
    dialog.getByRole("button", { name: "Create dataset", exact: true }),
  );
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await activate(
    page,
    page.getByRole("link", { name: "Build workflow", exact: true }),
  );
  await activate(
    page,
    page.getByRole("button", { name: "Save workflow", exact: true }),
  );
  await expect(
    page.getByRole("button", { name: "Launch run", exact: true }),
  ).toBeEnabled();
  await activate(
    page,
    page.getByRole("button", { name: "Launch run", exact: true }),
  );
  await activate(
    page,
    page.getByRole("button", { name: "Confirm & launch", exact: true }),
  );
  const exportButton = page.getByRole("button", {
    name: "Export JSONL",
    exact: true,
  });
  await expect(exportButton).toBeVisible({ timeout: 60000 });
  const event = page.waitForEvent("download");
  await activate(page, exportButton);
  const file = await (await event).path();
  expect(readFileSync(file!, "utf8").trim().split("\n")).toHaveLength(100);
});
