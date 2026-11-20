import { afterAll, beforeAll, expect, test } from "bun:test"
import { resolve } from "node:path"

const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? "playwright")
const project = resolve(import.meta.dir, "../../..")
let browser: Awaited<ReturnType<typeof chromium.launch>>
let server: ReturnType<typeof Bun.serve>
const boundaries: Record<string, string> = {
  "@utils/config": `export const REQUEST_BODY_MAX_SIZE=1024;`,
  "@map/layers/layers": `export const addMapLayer=()=>{}; export const removeMapLayer=()=>{};`,
  "@proto/shared_pb": `export const StandardFeedbackDetail_Severity={};`,
  "@utils/password-transmission": `export const createPasswordTransformState=()=>({collect:async()=>({}),tryUpdateSchema:()=>false});`,
  "@utils/rpc": `export const fromBinaryValid=()=>null; export const connectErrorToStandardFeedback=()=>null; export const connectErrorToMessage=e=>e.rawMessage; export const rpcUnary=()=>async(request)=>{window.uploads++;window.uploadSize=request.image.length;if(window.failUpload)throw new Error('Image could not be read. Please choose a valid image.');return {};};`,
}

beforeAll(async () => {
  const build = await Bun.build({
    entrypoints: [resolve(import.meta.dir, "image-upload.fixture.tsx")],
    target: "browser",
    plugins: [
      {
        name: "boundaries",
        setup(builder) {
          builder.onResolve(
            {
              filter:
                /^(@utils\/(config|rpc|password-transmission)|@map\/layers\/layers|@proto\/shared_pb)$/,
            },
            ({ path }) => ({ path, namespace: "boundary" }),
          )
          builder.onLoad({ filter: /.*/, namespace: "boundary" }, ({ path }) => ({
            contents: boundaries[path]!,
            loader: "ts",
            resolveDir: project,
          }))
        },
      },
    ],
  })
  if (!build.success) throw new AggregateError(build.logs, "Fixture build failed")
  const script = await build.outputs[0]!.text()
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
      return new Response(
        `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><style>main{max-width:520px;margin:24px auto;padding:12px}</style></head><body><main></main><script type="module" src="/fixture.js"></script></body></html>`,
        { headers: { "Content-Type": "text/html" } },
      )
    },
  })
  browser = await chromium.launch({ headless: true, channel: "chrome" })
}, 30000)
afterAll(async () => {
  await browser?.close()
  server?.stop(true)
})

const pageFor = async (width = 1280) => {
  const page = await browser.newPage({ viewport: { width, height: 800 } })
  await page.goto(server.url.toString())
  await page.getByRole("button", { name: "Upload image", exact: true }).waitFor()
  await page.waitForTimeout(50)
  return page
}
const file = (size: number) => ({
  name: "photo.png",
  mimeType: "image/png",
  buffer: Buffer.alloc(size, 7),
})

test("oversized uploads show visible standard feedback before reading bytes or making RPC", async () => {
  for (const width of [1280, 390]) {
    const page = await pageFor(width)
    try {
      await page.locator("input").setInputFiles(file(1025))
      await page.getByRole("alert").waitFor({ timeout: 1500 })
      expect(await page.getByRole("alert").textContent()).toContain(
        "Image file is too large",
      )
      expect(await page.evaluate(() => (window as any).uploads)).toBe(0)
      expect(await page.evaluate(() => (window as any).bytesRead)).toBe(0)
      expect(
        await page
          .locator("input")
          .evaluate((input: HTMLInputElement) => input.files!.length),
      ).toBe(0)
      const box = await page.getByRole("alert").boundingBox()
      expect(box!.x + box!.width).toBeLessThanOrEqual(width)
      if (process.env.IMAGE_UPLOAD_SCREENSHOT_DIR)
        await page.screenshot({
          path: resolve(
            process.env.IMAGE_UPLOAD_SCREENSHOT_DIR,
            `osm-ng-31-upload-${width}.png`,
          ),
        })
      await page.locator("input").setInputFiles(file(3))
      await page.waitForFunction(() => (window as any).uploads === 1)
      expect(await page.evaluate(() => (window as any).uploadSize)).toBe(3)
    } finally {
      await page.close()
    }
  }
})

test("a file at the server byte limit is not rejected as the compressed output limit", async () => {
  const page = await pageFor()
  try {
    await page.locator("input").setInputFiles(file(1024))
    await page.waitForFunction(() => (window as any).uploads === 1)
    expect(await page.evaluate(() => (window as any).uploadSize)).toBe(1024)
    expect(await page.getByRole("alert").count()).toBe(0)
  } finally {
    await page.close()
  }
})

test("backend errors remain friendly and the same file can be selected again", async () => {
  const page = await pageFor()
  try {
    await page.evaluate(() => {
      ;(window as any).failUpload = true
    })
    await page.locator("input").setInputFiles(file(8))
    await page.getByRole("alert").waitFor({ timeout: 1500 })
    expect(await page.getByRole("alert").textContent()).toContain(
      "Image could not be read",
    )
    expect(
      await page
        .locator("input")
        .evaluate((input: HTMLInputElement) => input.files!.length),
    ).toBe(0)
    await page.evaluate(() => {
      ;(window as any).failUpload = false
    })
    await page.locator("input").setInputFiles(file(8))
    await page.waitForFunction(() => (window as any).uploads === 2)
    expect(await page.evaluate(() => (window as any).uploadSize)).toBe(8)
  } finally {
    await page.close()
  }
})
