import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function expectNoSeriousOrCriticalAxeIssues(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).analyze();
  const severe = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical"
  );
  expect(
    severe,
    `Axe serious/critical violations on ${label}: ${JSON.stringify(
      severe.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        nodes: v.nodes.map((n) => n.html),
      })),
      null,
      2
    )}`
  ).toEqual([]);
}

test.describe("Silent Claim offline E2E demo & accessibility", () => {
  test("runs the flood, taps consent, approves batch, shows 7 refund lines, and passes axe on all 4 pages", async ({
    page,
    request,
  }) => {
    await request.post("http://127.0.0.1:8000/api/scenario/reset");

    await page.goto("/console", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: "SILENT CLAIM" })
    ).toBeVisible();
    await expect(page.getByText("Rules 2026.11-a")).toBeVisible();

    await page
      .getByRole("button", { name: /Reset and run the flood/i })
      .click();

    await expect(
      page.getByText(/6 of 7 claims filed \(awaiting Selvi's tap\)/i)
    ).toBeVisible({ timeout: 35_000 });
    await expectNoSeriousOrCriticalAxeIssues(page, "/console");

    await page.goto("/merchant", { waitUntil: "networkidle" });
    await expect(
      page.getByText(
        "உங்கள் கடையின் 28 நாள் வருமானம், தெருவில் மூடிய கடைகளின் எண்ணிக்கை, மழை அளவு மட்டுமே காப்பீட்டு நிறுவனத்துக்கு அனுப்பப்படும்."
      )
    ).toBeVisible();
    await expectNoSeriousOrCriticalAxeIssues(page, "/merchant (Ask)");

    await page
      .getByRole("button", { name: /ஆம், பதிவு செய்யுங்கள்/i })
      .click();
    await expect(
      page.getByRole("heading", { name: "Claim filed" })
    ).toBeVisible();
    await expect(page.getByText("Forms filled")).toBeVisible();

    await page.goto("/adjuster", { waitUntil: "networkidle" });
    await expect(
      page.getByText(
        "Eligibility and payout caps come from fixed, tested rules (2026.11-a). No AI decides money."
      )
    ).toBeVisible();

    const approveBtn = page.getByRole("button", {
      name: /Approve batch \(7\)/i,
    });
    await expect(approveBtn).toBeEnabled();
    await expectNoSeriousOrCriticalAxeIssues(page, "/adjuster");

    await approveBtn.click();
    await expect(page.getByText("Batch for 21 Oct: approved")).toBeVisible();
    await expect(page.getByText("7 of 7")).toBeVisible();

    await page.goto("/console", { waitUntil: "networkidle" });
    await expect(page.getByText("Batch for 21 Oct: approved")).toBeVisible();
    await expect(page.getByText("7 processed")).toBeVisible();
    await expect(page.getByText(/plan fee ->/i)).toHaveCount(7);

    await page.goto("/privacy", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: "PRIVACY NOTICE" })
    ).toBeVisible();
    await expectNoSeriousOrCriticalAxeIssues(page, "/privacy");
  });

  test("declines consent via வேண்டாம் (No), files no claim for Selvi, and forms a 6-claim batch", async ({
    page,
    request,
  }) => {
    await request.post("http://127.0.0.1:8000/api/scenario/reset");
    await request.post("http://127.0.0.1:8000/api/scenario/run", {
      data: { day: "2026-10-21", speed: 0 },
    });

    await page.goto("/merchant", { waitUntil: "networkidle" });
    const declineBtn = page.getByRole("button", { name: /வேண்டாம்/i });
    await expect(declineBtn).toBeVisible();
    await declineBtn.click();

    await expect(
      page.getByText("You chose not to file a claim for today.")
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Claim filed" })
    ).toHaveCount(0);

    await page.goto("/adjuster", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("button", { name: /Approve batch \(6\)/i })
    ).toBeEnabled();
    await expect(page.getByText("6 claims")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Flower stall" })).toHaveCount(
      0
    );
  });
});

