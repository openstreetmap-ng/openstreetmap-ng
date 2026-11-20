import { afterAll, beforeAll, expect, test } from "bun:test"
import { dirname, resolve } from "node:path"
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
const root = resolve(import.meta.dir, "../../..")
let browser, server
beforeAll(async () => {
  const translations = Bun.YAML.parse(
    await Bun.file(resolve(root, "config/locale/extra_en.yaml")).text(),
  )
  const boundaries = {
    "@diff-translations": `export default ${JSON.stringify(translations)}`,
    "@utils/rpc": "export const rpcUnary=()=>window.loadVersion;",
    "@map/layers/layers": "export const addMapLayer=()=>{};export const removeMapLayer=()=>{};",
  }
  const build = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "fixture.tsx")],
    target: "browser",
    plugins: [
      {
        name: "boundaries",
        setup(b) {
          b.onResolve({ filter: /.*/ }, ({ path }) =>
            path in boundaries ? { path, namespace: "boundary" } : undefined,
          )
          b.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents: boundaries[path],
            loader: "ts",
            resolveDir: root,
          }))
          b.onLoad({ filter: /_changeset-diff-control\.tsx$|fixture\.tsx$/ }, async ({ path }) => ({
            contents: "/** @jsxImportSource preact */\n" + (await Bun.file(path).text()),
            loader: "tsx",
            resolveDir: dirname(path),
          }))
        },
      },
    ],
  })
  if (!build.success) throw new AggregateError(build.logs)
  const script = await build.outputs[0].text()
  server = Bun.serve({
    port: 0,
    fetch(req) {
      const path = new URL(req.url).pathname
      if (path === "/app.js")
        return new Response(script, { headers: { "Content-Type": "text/javascript" } })
      if (path === "/bootstrap.css")
        return new Response(
          Bun.file(resolve(root, "node_modules/bootstrap/dist/css/bootstrap.min.css")),
        )
      if (path === "/map.css")
        return new Response(
          Bun.file(resolve(root, "node_modules/maplibre-gl/dist/maplibre-gl.css")),
        )
      return new Response(
        '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><link rel="stylesheet" href="/map.css"><style>body{margin:0}main{position:absolute;z-index:2;top:10px;left:10px;width:min(340px,calc(100% - 20px));padding:12px;background:white}#map{position:absolute;inset:0}</style><div id="map"></div><main></main><script type="module" src="/app.js"></script>',
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  browser = await chromium.launch({
    headless: true,
    channel: "chrome",
    args: ["--enable-webgl", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
  })
})
afterAll(async () => {
  await browser?.close()
  server?.stop(true)
})

for (const width of [1280, 390])
  test(`real MapLibre diff lifecycle at ${width}px`, async () => {
    const page = await browser.newPage({ viewport: { width, height: 800 } })
    await page.goto(String(server.url))
    await page.getByRole("button", { name: "Open changeset diff", exact: true }).click()
    await page.waitForFunction(async () => {
      const source = window.map.getSource("changeset-diff")
      return source && (await source.getData()).features.length === 6
    })
    await page.waitForFunction(
      () =>
        window.map.loaded() &&
        window.map.queryRenderedFeatures({ layers: ["changeset-diff-point"] }).length > 0,
    )
    expect(await page.evaluate(() => window.calls)).toEqual(
      expect.arrayContaining([
        { id: "1", version: "1", type: 0 },
        { id: "1", version: "2", type: 0 },
        { id: "2", version: "2", type: 0 },
        { id: "3", version: "1", type: 0 },
      ]),
    )
    const pixels = await page.evaluate(() => {
      const map = window.map
      map.triggerRepaint()
      const gl = map.getCanvas().getContext("webgl2")
      const bytes = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4)
      gl.readPixels(
        0,
        0,
        gl.drawingBufferWidth,
        gl.drawingBufferHeight,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        bytes,
      )
      let colors = 0
      for (let i = 0; i < bytes.length; i += 4)
        if (
          (bytes[i] > 130 && bytes[i + 1] < 120) ||
          (bytes[i + 1] > bytes[i] * 1.5 && bytes[i + 1] > bytes[i + 2])
        )
          colors++
      return colors
    })
    expect(pixels).toBeGreaterThan(50)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.evaluate(() =>
      window.map.setStyle({
        version: 8,
        sources: {},
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#f0f3f1" } },
        ],
      }),
    )
    await page.waitForFunction(async () => {
      const source = window.map.getSource("changeset-diff")
      return source && (await source.getData()).features.length === 6
    })
    await page.screenshot({
      path: resolve(
        process.env.EVIDENCE_DIR ?? "E:/makemoney/payout/evidence",
        `osm-ng-7-${width}.png`,
      ),
    })
    await page.getByRole("button", { name: "Before", exact: true }).click()
    await page.waitForFunction(async () => {
      const source = window.map.getSource("changeset-diff")
      return source && (await source.getData()).features.length === 3
    })
    await page.getByRole("button", { name: "Close changeset diff", exact: true }).click()
    await page.waitForFunction(() => !window.map.getSource("changeset-diff"))
    expect(await page.evaluate(() => !!window.map.getSource("changeset-diff"))).toBe(false)
    await page.evaluate(() => {
      window.fail = true
    })
    await page.getByRole("button", { name: "Open changeset diff", exact: true }).click()
    await page.getByRole("button", { name: "Retry", exact: true }).waitFor()
    await page.evaluate(() => {
      window.fail = false
    })
    await page.getByRole("button", { name: "Retry", exact: true }).click()
    await page.waitForFunction(async () => {
      const source = window.map.getSource("changeset-diff")
      return source && (await source.getData()).features.length === 3
    })
    await page.evaluate(() => {
      window.unmount()
    })
    await page.waitForFunction(() => !window.map.getSource("changeset-diff"))
    expect(await page.evaluate(() => !!window.map.getSource("changeset-diff"))).toBe(false)
    await page.close()
  }, 30000)

test("in-flight exit cancels and a large changeset never starts RPC", async () => {
  const page = await browser.newPage()
  await page.goto(String(server.url))
  await page.getByRole("button", { name: "Open changeset diff", exact: true }).waitFor()
  await page.evaluate(() => {
    window.delay = 500
  })
  await page.getByRole("button", { name: "Open changeset diff", exact: true }).click()
  await page.getByRole("button", { name: "Close changeset diff", exact: true }).click()
  expect(await page.evaluate(() => window.aborted)).toBeGreaterThan(0)
  await page.evaluate(() => {
    window.calls = []
    window.mount(true)
  })
  await page.getByRole("button", { name: "Open changeset diff", exact: true }).click()
  await page.getByText(/supports up to 200/).waitFor()
  expect(await page.evaluate(() => window.calls.length)).toBe(0)
  await page.close()
}, 30000)
