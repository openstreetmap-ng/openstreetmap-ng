import { afterAll, beforeAll, expect, test } from "bun:test"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
const url = process.env.SOFTWARE_URL
if (!url) throw new Error("Start probe.py --serve and set SOFTWARE_URL")
let browser: Awaited<ReturnType<typeof chromium.launch>>
beforeAll(async () => {
  browser = await chromium.launch({ headless: true, channel: "chrome" })
})
afterAll(async () => {
  await browser?.close()
})

for (const width of [1280, 390]) {
  test(`real GET filters, reset, images and layout at ${width}px`, async () => {
    const page = await browser.newPage({
      viewport: { width, height: 900 },
      javaScriptEnabled: false,
    })
    await page.goto(url + "/software")
    expect(await page.locator("article").count()).toBe(4)
    await page.locator("img").evaluateAll(async (images) => {
      await Promise.all(
        images.map((img) =>
          img.complete
            ? undefined
            : new Promise((resolve) => {
                img.onload = resolve
                img.onerror = resolve
              }),
        ),
      )
    })
    expect(
      await page
        .locator("img")
        .evaluateAll((images) =>
          images.every((img) => img.naturalWidth > 0 && img.naturalHeight > 0),
        ),
    ).toBe(true)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true)
    if (process.env.SOFTWARE_SCREENSHOTS)
      await page.screenshot({
        path: `${process.env.SOFTWARE_SCREENSHOTS}-${width}.png`,
        fullPage: true,
      })
    await page.getByLabel("Category", { exact: true }).selectOption("editing")
    await page.getByLabel("Operating system", { exact: true }).selectOption("windows")
    await page.getByLabel("License", { exact: true }).selectOption("open")
    await page.getByLabel("Maintenance", { exact: true }).selectOption("active")
    await Promise.all([
      page.waitForURL("**/software?**"),
      page.getByRole("button", { name: "Apply filters", exact: true }).click(),
    ])
    expect(
      await page
        .locator("article")
        .evaluateAll((items) => items.map((item) => item.dataset.software)),
    ).toEqual(["josm"])
    expect(
      await page.getByLabel("Operating system", { exact: true }).inputValue(),
    ).toBe("windows")
    await page.reload()
    expect(await page.locator("article").count()).toBe(1)
    await page.getByLabel("Category", { exact: true }).selectOption("navigation")
    await Promise.all([
      page.waitForURL("**category=navigation**"),
      page.getByRole("button", { name: "Apply filters", exact: true }).click(),
    ])
    expect(await page.locator("article").count()).toBe(0)
    expect(
      await page
        .getByText("No projects match these filters.", { exact: false })
        .count(),
    ).toBe(1)
    await page.getByRole("link", { name: "Reset filters", exact: true }).first().click()
    expect(await page.locator("article").count()).toBe(4)
    expect(new URL(page.url()).search).toBe("")
    await page.close()
  }, 20000)
}
