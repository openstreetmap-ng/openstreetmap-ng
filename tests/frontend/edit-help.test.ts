import { afterAll, beforeAll, expect, test } from "bun:test"
import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

const require = createRequire(
  process.env.FRONTEND_TEST_NODE_MODULES
    ? resolve(process.env.FRONTEND_TEST_NODE_MODULES, "../package.json")
    : import.meta.url,
)
const { build } = require("esbuild")
const { chromium } = require("playwright")
let browser: any
let server: ReturnType<typeof Bun.serve>
let origin: string

beforeAll(async () => {
  const fixture = resolve(import.meta.dir, "fixtures/edit-help.ts")
  const result = await build({
    entryPoints: [resolve(import.meta.dir, "fixtures/edit-help-entry.ts")],
    bundle: true,
    write: false,
    format: "iife",
    nodePaths: (process.env.NODE_PATH ?? "").split(
      process.platform === "win32" ? ";" : ":",
    ),
    alias: {
      "@zod/zod/mini": require.resolve("zod/mini"),
      ...Object.fromEntries(
        [
          "@std/assert",
          "@std/collections/map-not-nullish",
          "@std/collections/sum-of",
          "@std/text/unstable-trim-by",
          "@utils/path-codecs",
          "@utils/dom-helpers",
          "@index/remote-edit",

          "@std/assert/unstable-never",
          "@utils/config",
          "@map/layers/layers",
          "@utils/local-storage",

          "i18next",
        ].map((name) => [name, fixture]),
      ),
    },
    plugins: [
      {
        name: "navbar-state",
        setup(b: any) {
          b.onResolve({ filter: /navbar-left-state$/ }, () => ({ path: fixture }))
        },
      },
    ],
  })
  const css = readFileSync(require.resolve("bootstrap/dist/css/bootstrap.css"))
  server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch(request) {
      const pathname = new URL(request.url).pathname
      if (pathname === "/bundle.js")
        return new Response(result.outputFiles[0].contents, {
          headers: { "Content-Type": "text/javascript" },
        })
      if (pathname === "/style.css")
        return new Response(css, { headers: { "Content-Type": "text/css" } })
      if (pathname.startsWith("/static/")) return new Response(null, { status: 204 })
      return new Response(
        `<!doctype html><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/style.css">
      <nav class="navbar navbar-expand-lg"><button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#menu">Menu</button>
      <div id="menu" class="collapse navbar-collapse"><div id="NavbarLeft"></div></div></nav>
      <main style="height:600px">Map</main><script src="/bundle.js"></script>`,
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  origin = `http://127.0.0.1:${server.port}`
  browser = await chromium.launch({ headless: true })
})

afterAll(async () => {
  await browser?.close()
  server?.stop()
})

const open = async (query: string, mobile = false) => {
  const page = await browser.newPage({
    viewport: { width: mobile ? 390 : 1280, height: 800 },
    isMobile: mobile,
    hasTouch: mobile,
  })
  const errors: string[] = []
  page.on("pageerror", (error: Error) => errors.push(error.message))
  await page.route("**/*", (route: any) =>
    route.request().url().startsWith(origin) ? route.continue() : route.abort(),
  )
  await page.goto(`${origin}/${query}`)
  await page.locator(".edit-link.default").waitFor({ state: "attached" })
  return { page, errors }
}

for (const mobile of [false, true]) {
  test(`edit help displays and dismisses with URL preservation (mobile=${mobile})`, async () => {
    const { page, errors } = await open("?other=keep&edit_help=1#map=15/1/2", mobile)
    try {
      await page.locator(".tooltip.show").waitFor()
      expect(await page.locator(".tooltip-inner").innerText()).toContain(
        "Move the map and zoom",
      )
      if (process.env.EDIT_HELP_EVIDENCE)
        await page.screenshot({
          path: resolve(
            process.env.EDIT_HELP_EVIDENCE,
            mobile ? "mobile.png" : "desktop.png",
          ),
        })
      if (mobile)
        expect(await page.locator("#menu").getAttribute("class")).toContain("show")
      await page.evaluate(() => history.replaceState({ retained: 1 }, ""))
      await page.locator("main").click()
      expect(await page.locator(".tooltip").count()).toBe(0)
      expect(new URL(page.url()).search).toBe("?other=keep")
      expect(new URL(page.url()).hash).toBe("#map=15/1/2")
      expect(await page.evaluate(() => history.state)).toEqual({ retained: 1 })
      expect(await page.evaluate(() => (window as any).routerCtx.value.search)).toBe(
        "?other=keep",
      )
      await page.evaluate(() =>
        (window as any).navigate("/?other=keep&edit_help=1#map=15/1/2"),
      )
      await page.locator(".tooltip.show").waitFor()
      expect(errors).toEqual([])
    } finally {
      await page.close()
    }
  })
}

for (const query of [
  "",
  "?edit_help=0",
  "?edit_help=true",
  "?edit_help=1&loggedOut=1",
]) {
  test(`no tutorial for ${query || "absent query"}`, async () => {
    const { page, errors } = await open(query)
    try {
      await page.waitForTimeout(250)
      expect(await page.locator(".tooltip").count()).toBe(0)
      expect(new URL(page.url()).search).toBe(query)
      expect(errors).toEqual([])
    } finally {
      await page.close()
    }
  })
}

test("disabled zoom shows help exclusively, then restores the disabled hint", async () => {
  const { page, errors } = await open("?edit_help=1&disabled=1")
  try {
    await page.locator(".tooltip.show").waitFor()
    await page.locator(".edit-group").hover()
    expect(await page.locator(".tooltip").count()).toBe(1)
    expect(await page.locator(".tooltip-inner").innerText()).toContain("Move the map")
    await page.locator("main").click()
    await page.locator(".edit-group").hover()
    await page.waitForTimeout(250)
    expect(await page.locator(".tooltip-inner").innerText()).toBe(
      "javascripts.site.edit_disabled_tooltip",
    )
    await page.evaluate(() => {
      ;(window as any).editDisabled.value = false
    })
    await page.waitForTimeout(250)
    expect(await page.locator(".tooltip").count()).toBe(0)
    expect(errors).toEqual([])
  } finally {
    await page.close()
  }
})

test("navigation disposes help and its click handler, and subsequent navigation can activate it", async () => {
  const { page, errors } = await open("?edit_help=1")
  try {
    await page.locator(".tooltip.show").waitFor()
    await page.evaluate(() =>
      (window as any).navigate("/history?edit_help=0&keep=yes#map=14/2/3"),
    )
    await page.waitForTimeout(150)
    expect(await page.locator(".tooltip").count()).toBe(0)
    await page.locator("main").click()
    expect(new URL(page.url()).search).toBe("?edit_help=0&keep=yes")
    await page.evaluate(() => (window as any).navigate("/?edit_help=1"))
    await page.locator(".tooltip.show").waitFor()
    expect(await page.locator(".tooltip").count()).toBe(1)
    expect(errors).toEqual([])
  } finally {
    await page.close()
  }
})

test("unmount disposes the tooltip without consuming the query parameter", async () => {
  const { page, errors } = await open("?edit_help=1&keep=yes")
  try {
    await page.locator(".tooltip.show").waitFor()
    await page.evaluate(() => (window as any).unmount())
    expect(await page.locator(".tooltip").count()).toBe(0)
    await page.locator("main").click()
    expect(new URL(page.url()).search).toBe("?edit_help=1&keep=yes")
    expect(errors).toEqual([])
  } finally {
    await page.close()
  }
})
