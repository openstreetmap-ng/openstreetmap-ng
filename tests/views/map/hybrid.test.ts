import { afterAll, beforeAll, expect, test } from "bun:test"
import { resolve } from "node:path"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
let browser: Awaited<ReturnType<typeof chromium.launch>>
let server: ReturnType<typeof Bun.serve>
const project = resolve(import.meta.dir, "../../..")

beforeAll(async () => {
  const bundle = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "hybrid.fixture.ts")],
    target: "browser",
    plugins: [
      {
        name: "runtime-boundaries",
        setup(build) {
          build.onResolve(
            { filter: /^(@runtime\/theme|@utils\/local-storage)$/ },
            ({ path }) => ({ path, namespace: "boundary" }),
          )
          build.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents:
              path === "@runtime/theme"
                ? `import {signal} from '@preact/signals'; export const effectiveTheme=signal('light');`
                : `import {signal} from '@preact/signals'; export const overlayOpacityStorage=()=>signal(0.25);`,
            loader: "ts",
            resolveDir: project,
          }))
        },
      },
    ],
  })
  if (!bundle.success) throw new AggregateError(bundle.logs, "Fixture build failed")
  const script = await bundle.outputs[0]!.text()
  server = Bun.serve({
    port: 0,
    fetch(request) {
      const path = new URL(request.url).pathname
      if (path === "/fixture.js")
        return new Response(script, { headers: { "Content-Type": "text/javascript" } })
      if (path === "/map.css")
        return new Response(
          Bun.file(resolve(project, "node_modules/maplibre-gl/dist/maplibre-gl.css")),
        )
      return new Response(
        `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/map.css"><style>html,body,#map{margin:0;width:100%;height:100%}</style></head><body><div id="map"></div><script type="module" src="/fixture.js"></script></body></html>`,
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  browser = await chromium.launch({
    headless: true,
    channel: "chrome",
    args: ["--enable-unsafe-swiftshader"],
  })
}, 30000)

afterAll(async () => {
  await browser?.close()
  server?.stop(true)
})

test("hybrid is a selectable base layer in the real registry", async () => {
  const page = await browser.newPage()
  try {
    await page.goto(server.url.toString())
    await page.waitForFunction(() => "hybridTest" in window)
    expect(await page.evaluate(() => (window as any).hybridTest.exists)).toBe(true)
  } finally {
    await page.close()
  }
})

if (process.env.HYBRID_LIVE_RENDER === "1")
  test("live imagery and vector overlays render and survive switching on desktop/mobile", async () => {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 800 } })
      try {
        await page.goto(server.url.toString())
        await page.waitForFunction(() => "hybridTest" in window)
        await page.evaluate(() => (window as any).hybridTest.ready)
        const state = await page.evaluate(() => (window as any).hybridTest.snapshot())
        expect(state.active).toBe("hybrid")
        expect(state.layers[0].type).toBe("raster")
        expect(state.layers[0].paint["raster-opacity"]).toBe(1)
        expect(
          state.layers
            .slice(1)
            .every((layer: any) => ["line", "symbol", "circle"].includes(layer.type)),
        ).toBe(true)
        expect(state.features).toBeGreaterThan(0)
        expect(await page.evaluate(() => (window as any).hybridTest.lookup())).toBe(
          "hybrid",
        )
        const colors = await page
          .locator("canvas")
          .evaluate((canvas: HTMLCanvasElement) => {
            const copy = document.createElement("canvas")
            copy.width = canvas.width
            copy.height = canvas.height
            const ctx = copy.getContext("2d")!
            ctx.drawImage(canvas, 0, 0)
            const data = ctx.getImageData(0, 0, copy.width, copy.height).data
            const colors = new Set<number>()
            for (let i = 0; i < data.length; i += 400)
              colors.add((data[i]! << 16) | (data[i + 1]! << 8) | data[i + 2]!)
            return colors.size
          })
        expect(colors).toBeGreaterThan(100)
        if (process.env.HYBRID_SCREENSHOT_DIR)
          await page.screenshot({
            path: resolve(process.env.HYBRID_SCREENSHOT_DIR, `osm-ng-182-${width}.png`),
          })
        await page.evaluate(() => (window as any).hybridTest.switch("liberty"))
        expect(
          (
            await page.evaluate(() => (window as any).hybridTest.snapshot())
          ).layers.some((l: any) => l.id.startsWith("hybrid:")),
        ).toBe(false)
        await page.evaluate(() => (window as any).hybridTest.switch("hybrid"))
        expect(
          (await page.evaluate(() => (window as any).hybridTest.snapshot())).active,
        ).toBe("hybrid")
        expect(await page.evaluate(() => (window as any).hybridTest.errors)).toEqual([])
        const center = (
          await page.evaluate(() => (window as any).hybridTest.snapshot())
        ).center
        await page.evaluate(() => (window as any).hybridTest.pan())
        expect(
          (await page.evaluate(() => (window as any).hybridTest.snapshot())).center,
        ).not.toEqual(center)
      } finally {
        await page.close()
      }
    }
  }, 90000)
