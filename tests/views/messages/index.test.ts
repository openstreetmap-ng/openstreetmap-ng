import { afterAll, beforeAll, expect, test } from "bun:test"
import { resolve } from "node:path"
import { runMessageBatch } from "../../../app/views/messages/bulk"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
const root = resolve(import.meta.dir, "../../..")
let browser: Awaited<ReturnType<typeof chromium.launch>>
let server: ReturnType<typeof Bun.serve>
const locale = Bun.YAML.parse(
  await Bun.file(resolve(root, "config/locale/extra_en.yaml")).text(),
)
const baseLocale = Bun.YAML.parse(
  await Bun.file(resolve(root, "config/locale/download/en.yaml")).text(),
).en
const flatten = (
  value: Record<string, unknown>,
  prefix = "",
): Record<string, unknown> =>
  Object.fromEntries(
    Object.entries(value).flatMap(([key, entry]) => {
      const name = prefix ? `${prefix}.${key}` : key
      return entry && typeof entry === "object"
        ? Object.entries(flatten(entry as Record<string, unknown>, name))
        : [[name, entry]]
    }),
  )
const translations = { ...flatten(baseLocale), ...flatten(locale) }
const boundaries: Record<string, string> = {
  "@components/datetime-inputs": "export const Time=()=>null;",
  "@components/report": "export const ReportButton=()=>null;",
  "@components/user-link": "export const UserLink=()=>null;",
  "@proto/message_pb":
    "export const IndexPageSchema={};export const Service={method:{get:'get',getPage:'page',delete:'delete',updateReadState:'state'}};",
  "@utils/dom-helpers": "export const isUnmodifiedLeftClick=()=>true;",
  "@utils/path-codecs": "export const queryParam={positive:()=>0,positiveInt:()=>0};",
  "@utils/query-contract":
    "export const defineQueryContract=()=>({encode:()=>'?show=1'});",
  "@utils/query-signals": `import {signal} from '@preact/signals';const route=signal('inbox');const query=signal({});window.changeMailbox=v=>route.value=v;export const usePathSuffixQueryState=()=>({get value(){return route.value},query});`,
  "@utils/dispose-scope": `import {useSignalEffect} from '@preact/signals';export const useDisposeSignalEffect=fn=>useSignalEffect(()=>{const c=new AbortController();fn({signal:c.signal});return()=>c.abort()});`,
  "@utils/rpc": `export const connectErrorToMessage=e=>e.message;export const rpcUnary=method=>async req=>{window.calls.push({method,id:String(req.id),read:req.read});if(window.delay)await new Promise(r=>setTimeout(r,window.delay));if(window.failId===String(req.id))throw Error('denied');if(method==='get')return {sender:{},recipients:[],isRecipient:true,wasUnread:false,subject:'Preview',bodyRich:''};return {updated:window.updated!==false}};`,
  "../navbar/navbar": "export const changeUnreadMessagesBadge=n=>window.badge+=n;",
  "@utils/proto-page": `import {render} from 'preact';import i18next from 'i18next';i18next.init({lng:'en',keySeparator:false,resources:{en:{translation:${JSON.stringify(translations)}}},initImmediate:false});window.calls=[];window.badge=0;export const mountProtoPage=(_,Page)=>render(<Page/>,document.querySelector('main'));`,
  "@components/standard-pagination": `import {useSignal} from '@preact/signals';import {useEffect} from 'preact/hooks';export const StandardPagination=({children,onLoad,request})=>{const page=useSignal(1);useEffect(()=>{onLoad({messages:[1,2].map(n=>({id:BigInt((page.value-1)*2+n),unread:n===1,subject:'Message '+((page.value-1)*2+n),bodyPreview:'Preview',createdAt:1,recipients:[{}],recipientsCount:1,sender:{}}))})},[page.value,request.inbox]);return <><button onClick={()=>page.value=page.peek()===1?2:1}>Next page</button>{children()}</>};`,
}

beforeAll(async () => {
  const build = await Bun.build({
    entrypoints: [
      process.env.MAILBOX_SOURCE ?? resolve(root, "app/views/messages/index.tsx"),
    ],
    target: "browser",
    plugins: [
      {
        name: "boundaries",
        setup(b) {
          b.onResolve({ filter: /.*/ }, ({ path }) =>
            path in boundaries ? { path, namespace: "boundary" } : undefined,
          )
          b.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents: "/** @jsxImportSource preact */\n" + boundaries[path]!,
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
      if (path.startsWith("/fonts/"))
        return new Response(
          Bun.file(resolve(root, "node_modules/bootstrap-icons/font", path.slice(1))),
        )
      if (path === "/icons.css")
        return new Response(
          Bun.file(
            resolve(root, "node_modules/bootstrap-icons/font/bootstrap-icons.css"),
          ),
          { headers: { "Content-Type": "text/css" } },
        )
      if (path === "/app.js")
        return new Response(script, { headers: { "Content-Type": "text/javascript" } })
      if (path === "/bootstrap.css")
        return new Response(
          Bun.file(resolve(root, "node_modules/bootstrap/dist/css/bootstrap.min.css")),
        )
      return new Response(
        `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><link rel="stylesheet" href="/icons.css"><style>.social-entry.clickable{position:relative;padding-bottom:6px}.social-entry .body{padding:.375rem .3rem;overflow-wrap:anywhere}.btn-soft{background:var(--bs-tertiary-bg);border:1px solid var(--bs-border-color)}</style><main></main><script type="module" src="/app.js"></script>`,
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
const open = async (width = 1280) => {
  const p = await browser.newPage({ viewport: { width, height: 850 } })
  await p.goto(server.url.toString())
  await p.getByRole("heading", { name: "Message 1", exact: true }).waitFor()
  expect(
    await p
      .getByRole("checkbox", { name: "Select message: Message 1", exact: true })
      .count(),
  ).toBe(1)
  return p
}

test("batch preserves order and continues after failure", async () => {
  const calls: bigint[] = []
  const error = Error("denied")
  const errors = await runMessageBatch([1n, 2n, 3n], async (id) => {
    calls.push(id)
    if (id === 2n) throw error
  })
  expect(calls).toEqual([1n, 2n, 3n])
  expect(errors).toEqual([error])
  expect(
    await runMessageBatch([], async () => {
      throw error
    }),
  ).toEqual([])
})

test("actual page retains cross-page selection and deselects visible only", async () => {
  const p = await open()
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .check()
  await p.getByRole("button", { name: "Next page", exact: true }).click()
  await p
    .getByRole("checkbox", { name: "Select message: Message 3", exact: true })
    .check()
  expect(await p.getByRole("status").textContent()).toBe("Selected: 3")
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .check()
  expect(await p.getByRole("status").textContent()).toBe("Selected: 4")
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .uncheck()
  expect(await p.getByRole("status").textContent()).toBe("Selected: 2")
  await p.getByRole("button", { name: "Next page", exact: true }).click()
  expect(
    await p
      .getByRole("checkbox", { name: "Select message: Message 1", exact: true })
      .isChecked(),
  ).toBe(true)
  await p.close()
})

test("cross-page batch dispatches each selected ID once", async () => {
  const p = await open()
  await p
    .getByRole("checkbox", { name: "Select message: Message 1", exact: true })
    .check()
  await p.getByRole("button", { name: "Next page", exact: true }).click()
  await p
    .getByRole("checkbox", { name: "Select message: Message 3", exact: true })
    .check()
  await p
    .getByRole("button", { name: "Mark selected messages as unread", exact: true })
    .click()
  await p.waitForFunction(
    () => document.querySelector("[role=status]")?.textContent === "Selected: 0",
  )
  expect(await p.evaluate(() => window.calls)).toEqual([
    { method: "state", id: "1", read: false },
    { method: "state", id: "3", read: false },
  ])
  if (process.env.MAILBOX_DESKTOP_SCREENSHOT)
    await p.screenshot({ path: process.env.MAILBOX_DESKTOP_SCREENSHOT, fullPage: true })
  await p.close()
})

test("switching mailbox during a batch stops remaining requests", async () => {
  const p = await open()
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .check()
  await p.evaluate(() => {
    window.delay = 250
  })
  await p
    .getByRole("button", { name: "Mark selected messages as read", exact: true })
    .click()
  await p.evaluate(() => window.changeMailbox("outbox"))
  await p.waitForTimeout(350)
  expect(await p.evaluate(() => window.calls.map((c) => c.id))).toEqual(["1"])
  expect(await p.getByRole("status").textContent()).toBe("Selected: 0")
  expect(await p.getByRole("alert").count()).toBe(0)
  await p.close()
})

test("partial failures retain failed selections for retry and lock controls", async () => {
  const p = await open()
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .check()
  await p.evaluate(() => Object.assign(window, { failId: "2", delay: 120 }))
  await p
    .getByRole("button", { name: "Mark selected messages as read", exact: true })
    .click()
  expect(
    await p.getByRole("button", { name: "Clear selection", exact: true }).isDisabled(),
  ).toBe(true)
  await p.getByRole("alert").waitFor()
  expect(await p.getByRole("status").textContent()).toBe("Selected: 1")
  expect(
    await p
      .getByRole("checkbox", { name: "Select message: Message 1", exact: true })
      .isChecked(),
  ).toBe(false)
  expect(
    await p
      .getByRole("checkbox", { name: "Select message: Message 2", exact: true })
      .isChecked(),
  ).toBe(true)
  expect(await p.evaluate(() => window.calls.map((c) => c.id))).toEqual(["1", "2"])
  await p.evaluate(() => Object.assign(window, { failId: null, updated: false }))
  await p
    .getByRole("button", { name: "Mark selected messages as unread", exact: true })
    .click()
  await p.waitForFunction(
    () => document.querySelector("[role=status]")?.textContent === "Selected: 0",
  )
  expect(await p.getByRole("alert").count()).toBe(0)
  expect(await p.evaluate(() => window.badge)).toBe(-1)
  await p.close()
})

test("delete confirmation, failed-row retention, mailbox reset and mobile fit", async () => {
  const p = await open(390)
  await p
    .getByRole("checkbox", { name: "Select visible messages", exact: true })
    .check()
  p.once("dialog", (d) => d.dismiss())
  await p.getByRole("button", { name: "Delete selected messages", exact: true }).click()
  expect(await p.evaluate(() => window.calls.length)).toBe(0)
  await p.evaluate(() => {
    window.failId = "2"
  })
  p.once("dialog", (d) => d.accept())
  await p.getByRole("button", { name: "Delete selected messages", exact: true }).click()
  await p.getByRole("alert").waitFor()
  expect(
    await p
      .getByRole("checkbox", { name: "Select message: Message 1", exact: true })
      .count(),
  ).toBe(0)
  expect(await p.getByRole("status").textContent()).toBe("Selected: 1")
  if (process.env.MAILBOX_SCREENSHOT)
    await p.screenshot({ path: process.env.MAILBOX_SCREENSHOT, fullPage: true })
  expect(
    await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true)
  await p.evaluate(() => window.changeMailbox("outbox"))
  await p.waitForFunction(
    () => document.querySelector("[role=status]")?.textContent === "Selected: 0",
  )
  expect(
    await p
      .getByRole("button", { name: "Mark selected messages as read", exact: true })
      .count(),
  ).toBe(0)
  expect(await p.getByRole("alert").count()).toBe(0)
  await p.close()
})
