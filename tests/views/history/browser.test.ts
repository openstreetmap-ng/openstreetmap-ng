import { afterAll, beforeAll, expect, test } from "bun:test"
import { dirname, resolve } from "node:path"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
const root = resolve(import.meta.dir, "../../..")
const flatten = (
  value: Record<string, unknown>,
  prefix = "",
): Record<string, unknown> =>
  Object.fromEntries(
    Object.entries(value).flatMap(([key, entry]) => {
      const name = prefix ? `${prefix}.${key}` : key
      return entry && typeof entry === "object"
        ? Object.entries(flatten(entry as Record<string, unknown>, name))
        : [
            [
              name,
              typeof entry === "string"
                ? entry.replace(/%\{(\w+)\}/g, "{{$1}}")
                : entry,
            ],
          ]
    }),
  )
const translations = {
  ...flatten(
    Bun.YAML.parse(
      await Bun.file(resolve(root, "config/locale/download/en.yaml")).text(),
    ).en,
  ),
  ...flatten(
    Bun.YAML.parse(await Bun.file(resolve(root, "config/locale/extra_en.yaml")).text()),
  ),
}
let browser: Awaited<ReturnType<typeof chromium.launch>>
let server: ReturnType<typeof Bun.serve>
const boundaries: Record<string, string> = {
  "@history-locale": `export default ${JSON.stringify(translations)};`,
  "@components/bootstrap-wrappers": "export const BTooltip=({children})=>children;",
  "@components/standard-pagination": `import {updateUrl} from '@utils/url-state';export const PageOrder={desc_range:0};export const StandardPagination=({request})=>{window.calls.push({limit:request.limit,page:new URL(location.href).searchParams.get('page')});return <button onClick={()=>updateUrl(url=>url.searchParams.set('page','3'),'push')}>Next fixture page</button>};`,
  "@components/tags": "export const Tags=()=>null;",
  "@index/_action-sidebar":
    "export const SidebarHeader=({children})=><div>{children}</div>;",
  "@index/element":
    'export const ElementTypeParam={};export const ElementIdParam={};export const ElementLocation=()=>null;export const ElementMeta=()=>null;export const elementFocusPaint={};export const getElementTypeSlug=()=>"node";',
  "@index/router": "export const defineRoute=route=>route;",
  "@map/layers/focus-layer": "export const focusObjects=()=>{};",
  "@map/render-objects": "export const convertRenderElementsData=()=>[];",
  "@proto/element_pb": 'export const Service={method:{getHistory:"history"}};',
  "@proto/shared_pb": "export const ElementType={node:0,way:1,relation:2};",
  "@runtime/title": "export const setPageTitle=()=>{};",
  "@utils/local-storage": `import {signal} from '@preact/signals';export const tagsDiffStorage=signal(false);`,
  "@utils/config": "export const ELEMENT_HISTORY_PAGE_SIZE=10;",
}
beforeAll(async () => {
  const build = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "fixture.tsx")],
    target: "browser",
    plugins: [
      {
        name: "boundaries",
        setup(b) {
          b.onResolve({ filter: /^@history-under-test$/ }, () => ({
            path:
              process.env.HISTORY_SOURCE ??
              resolve(root, "app/views/index/element-history.tsx"),
            namespace: "history-source",
          }))
          b.onLoad({ filter: /.*/, namespace: "history-source" }, async ({ path }) => ({
            contents:
              "/** @jsxImportSource preact */\n" + (await Bun.file(path).text()),
            loader: "tsx",
            resolveDir: dirname(path),
          }))
          b.onResolve({ filter: /.*/ }, ({ path }) =>
            path in boundaries ? { path, namespace: "boundary" } : undefined,
          )
          b.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents: "/** @jsxImportSource preact */\n" + boundaries[path],
            loader: "tsx",
            resolveDir: root,
          }))
        },
      },
    ],
  })
  if (!build.success) throw new AggregateError(build.logs)
  const script = await build.outputs[0]!.text()
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
      return new Response(
        `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><main class="p-3" style="max-width:450px"></main><script type="module" src="/app.js"></script>`,
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  browser = await chromium.launch({ headless: true, channel: "chrome" })
})
afterAll(async () => {
  await browser?.close()
  server?.stop(true)
})

for (const width of [1280, 390])
  test(`actual sidebar limit, URL preservation and Back at${width}px`, async () => {
    const p = await browser.newPage({ viewport: { width, height: 800 } })
    await p.goto(server.url + "node/1/history?page=7&lat=1&lon=2&zoom=3#view")
    await p.getByRole("heading").first().waitFor()
    expect(
      await p.getByRole("combobox", { name: "Versions per page", exact: true }).count(),
    ).toBe(1)
    expect(
      await p
        .getByRole("combobox", { name: "Versions per page", exact: true })
        .inputValue(),
    ).toBe("10")
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("25")
    expect(await p.evaluate(() => window.calls.at(-1))).toEqual({
      limit: 25,
      page: null,
    })
    expect(new URL(p.url()).searchParams.get("lat")).toBe("1")
    expect(new URL(p.url()).searchParams.get("lon")).toBe("2")
    expect(new URL(p.url()).searchParams.get("zoom")).toBe("3")
    expect(new URL(p.url()).hash).toBe("#view")
    await p.getByRole("button", { name: "Next fixture page", exact: true }).click()
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("50")
    expect(new URL(p.url()).searchParams.has("page")).toBe(false)
    await p.goBack()
    expect(
      await p
        .getByRole("combobox", { name: "Versions per page", exact: true })
        .inputValue(),
    ).toBe("25")
    expect(new URL(p.url()).searchParams.get("page")).toBe("3")
    expect(await p.evaluate(() => window.calls.at(-1))).toEqual({
      limit: 25,
      page: "3",
    })
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("10")
    expect(new URL(p.url()).searchParams.has("limit")).toBe(false)
    expect(new URL(p.url()).searchParams.has("page")).toBe(false)
    expect(
      await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true)
    if (process.env.HISTORY_SCREENSHOTS)
      await p.screenshot({
        path: `${process.env.HISTORY_SCREENSHOTS}-${width}.png`,
        fullPage: true,
      })
    await p.close()
  }, 20000)

test("invalid URL values fall back to default; unsupported mutations are rejected", async () => {
  const p = await browser.newPage()
  await p.goto(server.url + "node/1/history?limit=999")
  await p.getByRole("combobox", { name: "Versions per page", exact: true }).waitFor()
  expect(
    await p.evaluate(() =>
      [null, "", "0", "-1", "1e2", " 25", "101", "999", "oops"].map(
        window.parseHistoryLimit,
      ),
    ),
  ).toEqual([10, 10, 10, 10, 10, 10, 10, 10, 10])
  expect(
    await p.evaluate(() => ["10", "25", "50", "100"].map(window.parseHistoryLimit)),
  ).toEqual([10, 25, 50, 100])
  expect(
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .inputValue(),
  ).toBe("10")
  expect(
    await p.evaluate(() => {
      try {
        window.changeHistoryLimit(new URL(location.href), 999)
        return false
      } catch {
        return true
      }
    }),
  ).toBe(true)
  await p.close()
})
