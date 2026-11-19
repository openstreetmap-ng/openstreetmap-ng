import { afterAll, beforeAll, expect, test } from "bun:test"
import { resolve } from "node:path"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
let browser: Awaited<ReturnType<typeof chromium.launch>>
let server: ReturnType<typeof Bun.serve>
const errors: string[] = []
const project = resolve(import.meta.dir, "../../..")
const modules: Record<string, string> = {
  "@utils/config": `export const isLoggedIn = !new URLSearchParams(location.search).has('signed_out');`,
  "@utils/local-storage": `import {signal} from '@preact/signals'; export const preferredEditorStorage = signal('id');`,
  "@map/main-map": `import {signal} from '@preact/signals'; export const mainMap = signal({});`,
  "@map/layers/layers": `export const addMapLayer = () => {}; export const removeMapLayer = () => {};`,
  "@map/state": `
    export const getInitialMapState = () => ({lon:1,lat:2,zoom:5,layersCode:''});
    export const encodeMapState = () => '#map=5/2/1';
    export const parseLonLatZoom = () => null;
  `,
  "@index/remote-edit": `export const RemoteEditButton = () => null;`,
}

beforeAll(async () => {
  const bundle = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "edit-help.fixture.ts")],
    target: "browser",
    plugins: [
      {
        name: "page-boundaries",
        setup(build) {
          build.onResolve(
            {
              filter:
                /^(@utils\/config|@utils\/local-storage|@map\/main-map|@map\/layers\/layers|@map\/state|@index\/remote-edit)$/,
            },
            ({ path }) => ({ path, namespace: "boundary" }),
          )
          build.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents: modules[path]!,
            loader: "tsx",
            resolveDir: project,
          }))
        },
      },
    ],
  })
  if (!bundle.success) throw new AggregateError(bundle.logs, "Fixture bundle failed")
  const script = await bundle.outputs[0]!.text()
  server = Bun.serve({
    port: 0,
    fetch(request) {
      const path = new URL(request.url).pathname
      if (path === "/fixture.js")
        return new Response(script, { headers: { "Content-Type": "text/javascript" } })
      if (path === "/bootstrap.css")
        return new Response(
          Bun.file(
            resolve(project, "node_modules/bootstrap/dist/css/bootstrap.min.css"),
          ),
        )
      if (path.startsWith("/static/img/")) return new Response(null, { status: 204 })
      return new Response(
        `<!doctype html><html lang="en"><head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="stylesheet" href="/bootstrap.css">
      <style>.navbar{padding:12px}.map-actions{max-width:360px}.map-actions img{display:none}main{height:550px;background:#e8eff0;padding:32px}</style>
      </head><body><nav class="navbar navbar-expand-lg"><div class="container-fluid">
      <span class="navbar-brand">OpenStreetMap</span>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-label="Menu">Menu</button>
      <div class="collapse navbar-collapse" id="navbarSupportedContent"><div id="NavbarLeft" class="map-actions btn-group d-flex"></div></div>
      </div></nav><main><a id="start" href="/?edit_help=1">Start mapping</a><div id="map-area" style="height:300px">Map boundary fixture</div></main>
      <script type="module" src="/fixture.js"></script></body></html>`,
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  browser = await chromium.launch({
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "chrome",
  })
}, 30000)

afterAll(async () => {
  await browser?.close()
  server?.stop(true)
})

const pageFor = async (query: string, width = 1280) => {
  const page = await browser.newPage({ viewport: { width, height: 800 } })
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(`${server.url}${query}`)
  await page.locator(".edit-link.default").waitFor({ state: "attached" })
  await page.waitForTimeout(100)
  return page
}

test("signed-in edit_help=1 displays the original edit-button tutorial", async () => {
  const page = await pageFor("?edit_help=1#map=5/2/1")
  try {
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    expect(await page.getByRole("tooltip").textContent()).toContain(
      "Move the map and zoom in",
    )
    const tip = await page.getByRole("tooltip").boundingBox()
    const anchor = await page.locator(".edit-link.default").boundingBox()
    expect(tip!.y).toBeGreaterThanOrEqual(anchor!.y + anchor!.height)
    expect(tip!.x).toBeGreaterThanOrEqual(0)
    expect(tip!.x + tip!.width).toBeLessThanOrEqual(1280)
    if (process.env.OSM_EDIT_HELP_SCREENSHOT_DIR)
      await page.screenshot({
        path: resolve(
          process.env.OSM_EDIT_HELP_SCREENSHOT_DIR,
          "osm-ng-28-desktop.png",
        ),
      })
  } finally {
    await page.close()
  }
})

test("first click dismisses, preserves other query/hash and replaces history", async () => {
  const page = await pageFor("?edit_help=1&keep=a&keep=b#map=5/2/1")
  try {
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    const length = await page.evaluate(() => history.length)
    await page.locator("#map-area").click()
    await page.waitForTimeout(50)
    expect(await page.getByRole("tooltip").count()).toBe(0)
    const url = new URL(page.url())
    expect(url.searchParams.has("edit_help")).toBe(false)
    expect(url.searchParams.getAll("keep")).toEqual(["a", "b"])
    expect(url.hash).toBe("#map=5/2/1")
    expect(await page.evaluate(() => history.length)).toBe(length)
  } finally {
    await page.close()
  }
})

test("signed-out, absent and non-1 requests do not activate the tutorial", async () => {
  for (const query of [
    "",
    "?edit_help=0",
    "?edit_help=true",
    "?signed_out=1&edit_help=1",
  ]) {
    const page = await pageFor(query)
    expect(await page.getByRole("tooltip").count()).toBe(0)
    await page.close()
  }
})

test("SPA re-entry can show the tutorial again after completion", async () => {
  const page = await pageFor("?edit_help=1")
  try {
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    await page.locator("#map-area").click()
    await page.locator("#start").click()
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    expect(new URL(page.url()).searchParams.get("edit_help")).toBe("1")
  } finally {
    await page.close()
  }
})

test("normal disabled-edit hover tooltip returns after completion", async () => {
  const page = await pageFor("?edit_help=1")
  try {
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    await page.locator("#map-area").click()
    await page.locator(".edit-group").hover()
    await page.waitForTimeout(250)
    expect(await page.getByRole("tooltip").textContent()).toContain("Zoom in to edit")
  } finally {
    await page.close()
  }
})

test("mobile tutorial waits for a visible edit control", async () => {
  const page = await pageFor("?edit_help=1", 390)
  try {
    expect(await page.getByRole("tooltip").count()).toBe(0)
    await page.getByRole("button", { name: "Menu", exact: true }).click()
    await page.getByRole("tooltip").waitFor({ timeout: 1500 })
    await page.waitForTimeout(100)
    const box = await page.getByRole("tooltip").boundingBox()
    const anchor = await page.locator(".edit-link.default").boundingBox()
    expect(box!.y).toBeGreaterThanOrEqual(anchor!.y + anchor!.height)
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(390)
    if (process.env.OSM_EDIT_HELP_SCREENSHOT_DIR)
      await page.screenshot({
        path: resolve(process.env.OSM_EDIT_HELP_SCREENSHOT_DIR, "osm-ng-28-mobile.png"),
      })
    await page.locator("#map-area").click()
    expect(new URL(page.url()).searchParams.has("edit_help")).toBe(false)
  } finally {
    await page.close()
  }
})

test("browser regression run has no uncaught page errors", () => {
  expect(errors).toEqual([])
})
