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
  "@components/tags": "export const Tags=()=>null;",
  "@index/_action-sidebar":
    "export const SidebarHeader=({children})=><div>{children}</div>;",
  "@index/element":
    'export const ElementTypeParam={};export const ElementIdParam={};export const ElementLocation=()=>null;export const ElementMeta=()=>null;export const elementFocusPaint={};export const getElementTypeSlug=()=>"node";',
  "@index/router": "export const defineRoute=route=>route;",
  "@map/layers/focus-layer": "export const focusObjects=()=>{};",
  "@map/layers/layers":
    "export const addMapLayer=()=>{};export const removeMapLayer=()=>{};",
  "@map/render-objects": "export const convertRenderElementsData=()=>[];",
  "@map/state":
    'export const encodeMapState=()=>"";export const parseLonLatZoom=()=>null;',
  "@runtime/title": "export const setPageTitle=()=>{};",
  "@utils/local-storage": `import {signal} from '@preact/signals';export const tagsDiffStorage=signal(false);`,
  "@utils/config":
    'export const ELEMENT_HISTORY_PAGE_SIZE=10;export const STANDARD_PAGINATION_DISTANCE=2;export const STANDARD_PAGINATION_MAX_FULL_PAGES=10;export const primaryLanguage="en";',
  "@utils/rpc": `import {create,toBinary,fromBinary} from '@bufbuild/protobuf';import {Code,ConnectError} from '@connectrpc/connect';import {StandardPaginationStateSchema} from '@proto/shared_pb';
    export const connectErrorToMessage=e=>e.message;
    export const rpcUnary=method=>async(request,{signal}={})=>{
      const wire=fromBinary(method.input,toBinary(method.input,create(method.input,request)));
      const call={limit:wire.limit,stateSize:wire.state?.state?.pageSize??null,page:wire.state?.requestedPage??1,aborted:false};window.calls.push(call);
      if(wire.limit===25)await new Promise(resolve=>setTimeout(resolve,500));
      if(signal?.aborted){call.aborted=true;throw new ConnectError('Aborted',Code.Canceled)}
      if(call.stateSize!==null&&call.stateSize!==wire.limit)throw Error('Mixed-size pagination cursor');
      const size=wire.limit||10;const numPages=Math.ceil(123/size);const currentPage=Math.min(call.page,numPages);const offset=(currentPage-1)*size;
      const state=create(StandardPaginationStateSchema,{cursors:{case:'u64',value:{snapshot:123n}},pageSize:size,currentPage,totalExtent:{case:'knownTotal',value:{numPages,numItems:123}},snapshotMaxId:123n});
      const elements=Array.from({length:Math.min(size,123-offset)},(_,i)=>({ref:{type:0,id:1n,version:123-offset-i},context:{render:{}}}));
      return create(method.output,{state,elements});
    };`,
}

beforeAll(async () => {
  const build = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "fixture.tsx")],
    target: "browser",
    plugins: [
      {
        name: "integration-boundaries",
        setup(b) {
          b.onResolve({ filter: /^@history-under-test$/ }, () => ({
            path: resolve(root, "app/views/index/element-history.tsx"),
            namespace: "history-source",
          }))
          b.onResolve({ filter: /^@components\/standard-pagination$/ }, () => ({
            path: resolve(root, "app/views/components/standard-pagination.tsx"),
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
  if (!build.success)
    throw new AggregateError(
      build.logs,
      "Generate web bindings with generate_web.py before this test",
    )
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
        `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><style>.version-badge{color:var(--bs-secondary-color);background:var(--bs-secondary-bg);font-size:initial}.action-sidebar.element-history a:not(.stretched-link),.action-sidebar.element-history button{position:relative;z-index:10}</style><main class="action-sidebar element-history p-3" style="max-width:450px"></main><script type="module" src="/app.js"></script>`,
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
  test(`real pagination cursor replacement, wire and stale response at${width}px`, async () => {
    const p = await browser.newPage({ viewport: { width, height: 900 } })
    await p.goto(server.url + "node/1/history?page=7&lat=1&lon=2#view")
    await p.waitForFunction(
      () => document.querySelectorAll(".version-section").length === 10,
    )
    expect(await p.evaluate(() => window.calls.at(-1))).toMatchObject({
      limit: 10,
      stateSize: null,
      page: 7,
    })
    expect(await p.locator('[aria-current="page"]').textContent()).toBe("63\u201054")
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("25")
    await p.waitForFunction(() => window.calls.some((call) => call.limit === 25))
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("50")
    await p.waitForFunction(
      () => document.querySelectorAll(".version-section").length === 50,
    )
    expect(await p.evaluate(() => window.calls.at(-1))).toMatchObject({
      limit: 50,
      stateSize: null,
      page: 1,
    })
    expect(await p.locator('[aria-current="page"]').textContent()).toBe("123\u201074")
    await p.waitForTimeout(600)
    expect(
      await p.evaluate(() => window.calls.find((call) => call.limit === 25)?.aborted),
    ).toBe(true)
    expect(await p.locator(".version-section").count()).toBe(50)
    expect(await p.locator(".version-badge").first().textContent()).toBe("Version 123")
    await p.getByRole("button", { name: "73\u201024", exact: true }).click()
    await p.waitForFunction(
      () =>
        document.querySelector('[aria-current="page"]')?.textContent === "73\u201024",
    )
    expect(await p.evaluate(() => window.calls.at(-1))).toMatchObject({
      limit: 50,
      stateSize: 50,
      page: 2,
    })
    await p
      .getByRole("combobox", { name: "Versions per page", exact: true })
      .selectOption("100")
    await p.waitForFunction(
      () => document.querySelectorAll(".version-section").length === 100,
    )
    expect(await p.evaluate(() => window.calls.at(-1))).toMatchObject({
      limit: 100,
      stateSize: null,
      page: 1,
    })
    expect(new URL(p.url()).searchParams.has("page")).toBe(false)
    await p.goBack()
    await p.waitForFunction(
      () =>
        document.querySelector('[aria-current="page"]')?.textContent === "73\u201024",
    )
    expect(await p.evaluate(() => window.calls.at(-1))).toMatchObject({
      limit: 50,
      stateSize: null,
      page: 2,
    })
    expect(
      await p
        .getByRole("combobox", { name: "Versions per page", exact: true })
        .inputValue(),
    ).toBe("50")
    expect(new URL(p.url()).searchParams.get("lat")).toBe("1")
    expect(new URL(p.url()).hash).toBe("#view")
    expect(await p.locator(".version-badge").first().textContent()).toBe("Version 73")
    expect(await p.getByRole("alert").count()).toBe(0)
    expect(
      await p.evaluate(() =>
        window.calls.every(
          (call) => call.stateSize === null || call.stateSize === call.limit,
        ),
      ),
    ).toBe(true)
    expect(
      await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true)
    if (process.env.HISTORY_INTEGRATION_SCREENSHOTS)
      await p.screenshot({
        path: `${process.env.HISTORY_INTEGRATION_SCREENSHOTS}-${width}.png`,
      })
    await p.close()
  }, 20000)
