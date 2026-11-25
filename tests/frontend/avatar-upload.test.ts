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
  const fixture = resolve(import.meta.dir, "fixtures/avatar-upload.ts")
  const result = await build({
    entryPoints: [resolve(import.meta.dir, "fixtures/avatar-upload-entry.tsx")],
    bundle: true,
    write: false,
    format: "iife",
    nodePaths: [process.env.FRONTEND_TEST_NODE_MODULES].filter(Boolean),
    alias: Object.fromEntries(
      [
        "@connectrpc/connect",
        "@proto/shared_pb",
        "@std/assert",
        "@std/media-types/parse-media-type",
        "@utils/config.macro",
        "@utils/password-transmission",
        "@utils/rpc",
        "@map/layers/layers",
        "i18next",
      ].map((name) => [name, fixture]),
    ),
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
      return new Response(
        '<!doctype html><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/style.css"><h1>Avatar upload</h1><div id="root"></div><script src="/bundle.js"></script>',
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
for (const field of ["avatar_file", "background_file"]) {
  for (const mobile of [false, true]) {
    test(`oversized ${field} gives feedback before reading or RPC, then permits retry (mobile=${mobile})`, async () => {
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
      try {
        await page.goto(`${origin}/?field=${field}`)
        await page.waitForTimeout(150)
        await page
          .locator("input[type=file]")
          .setInputFiles({
            name: "large.png",
            mimeType: "image/png",
            buffer: Buffer.alloc(9),
          })
        await page.getByRole("alert").waitFor()
        expect(await page.getByRole("alert").innerText()).toContain(
          "This file is too large",
        )
        expect(
          await page.evaluate(() => [
            (window as any).rpcCalls,
            (window as any).readCalls,
          ]),
        ).toEqual([0, 0])
        expect(await page.locator("fieldset").isDisabled()).toBe(false)
        if (process.env.AVATAR_EVIDENCE && field === "avatar_file")
          await page.screenshot({
            path: resolve(
              process.env.AVATAR_EVIDENCE,
              mobile ? "mobile.png" : "desktop.png",
            ),
          })
        await page
          .locator("input[type=file]")
          .setInputFiles({
            name: "small.png",
            mimeType: "image/png",
            buffer: Buffer.from([1, 2, 3, 4, 5, 6, 7, 8]),
          })
        await page.waitForFunction(() => (window as any).rpcCalls === 1)
        expect(await page.evaluate(() => (window as any).lastBytes)).toEqual([
          1, 2, 3, 4, 5, 6, 7, 8,
        ])
        expect(await page.getByRole("alert").count()).toBe(0)
        expect(errors).toEqual([])
      } finally {
        await page.close()
      }
    })
  }
}
test("empty file remains available for image removal/preset requests", async () => {
  const page = await browser.newPage()
  try {
    await page.goto(origin)
    await page.waitForTimeout(150)
    await page.getByRole("button", { name: "Upload" }).click()
    await page.waitForFunction(() => (window as any).rpcCalls === 1)
    expect(await page.evaluate(() => (window as any).lastBytes)).toEqual([])
    expect(await page.getByRole("alert").count()).toBe(0)
  } finally {
    await page.close()
  }
})
