import { execSync } from "node:child_process"
import { globSync, readFileSync, rmSync, statSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { assert } from "@std/assert"
import { parse as parseToml } from "@std/toml"
import legacy from "@vitejs/plugin-legacy"
import autoprefixer from "autoprefixer"
import { PurgeCSS } from "purgecss"
import { visualizer } from "rollup-plugin-visualizer"
import rtlcss from "rtlcss"
import Macros from "unplugin-macros/vite"
import { defineConfig, type PluginOption } from "vite"
import { browserslist } from "./package.json"

const CSS_FILE_RE = /\.(?:c|s[ac])ss$/i

// Content paths scanned for class usage
const CONTENT_PATHS = [
  "app/views/**/*.html.jinja",
  "app/views/**/*.ts",
  "app/views/**/*.tsx",
]

// Dynamic icons from config/socials.toml
const SOCIALS_ICONS = Object.entries(
  parseToml(readFileSync("config/socials.toml", "utf-8")),
).map(([service, config]) => `bi-${(config as { icon?: string }).icon ?? service}`)

const PURGECSS_SAFELIST = {
  standard: [
    // Bootstrap state classes
    "show",
    "fade",
    "active",
    "disabled",
    "collapsed",
    "collapsing",
    "visually-hidden",
    "invisible",
    // Form validation
    "was-validated",
    "is-valid",
    "is-invalid",
    // Bootstrap icons
    ...SOCIALS_ICONS,
  ],
  greedy: [
    // Bootstrap dynamic components
    /^modal/,
    /^offcanvas/,
    /^tooltip/,
    /^popover/,
    /^dropdown/,
    /^collapse/,
    /^nav-/,
    // Bootstrap utilities
    /^d-/,
    /^opacity-/,
    /^btn-/,
    // MapLibre GL
    /^maplibregl-/,
    // Project-specific dynamic classes
    /^activity-\d+$/,
    /^icon-\d+$/,
  ],
}
const PURGECSS_EXTRACTOR = (content: string) => content.match(/[\w-/:]+(?<!:)/g) ?? []

const trimDevBase = (base: string, path: string) =>
  path.startsWith(base) ? `/${path.slice(base.length)}` : path

const rewriteCssModule = (code: string, mutate: (css: string) => string) => {
  const START = 'const __vite__css = "'
  const END = '"\n__vite__updateStyle'

  const valueStart = code.indexOf(START)
  assert(valueStart >= 0)
  const contentStart = valueStart + START.length

  const contentEnd = code.indexOf(END, contentStart)
  assert(contentEnd >= 0)

  const original = Function(
    `"use strict";return "${code.slice(contentStart, contentEnd)}";`,
  )()
  const mutated = JSON.stringify(mutate(original)).slice(1, -1)
  return code.slice(0, contentStart) + mutated + code.slice(contentEnd)
}

export default defineConfig({
  appType: "custom",
  base: "/static/vite/",
  resolve: {
    alias: [
      {
        find: "@index",
        replacement: fileURLToPath(import.meta.resolve("./app/views/index")),
      },
      {
        find: "@lib",
        replacement: fileURLToPath(import.meta.resolve("./app/views/lib")),
      },
      {
        find: /^bootstrap$/,
        replacement: fileURLToPath(import.meta.resolve("bootstrap/js/index.esm.js")),
      },
    ],
  },
  clearScreen: false,
  server: {
    host: "localhost",
    port: 49568,
    strictPort: true,
    origin: "http://localhost:49568",
  },
  build: {
    manifest: true,
    outDir: "app/static/vite",
    copyPublicDir: false,
    sourcemap: true,
    assetsInlineLimit: 1024,
    modulePreload: { polyfill: false },
    rollupOptions: {
      input: {
        embed: "app/views/embed.ts",
        id: "app/views/id.ts",
        "main-sync": "app/views/main-sync.ts",
        main: "app/views/main.ts",
        rapid: "app/views/rapid.ts",
        "test-site": "app/views/test-site.ts",
      },
      output: {
        entryFileNames: "[name].[hash].js",
        chunkFileNames: "assets/[name].[hash].js",
        assetFileNames: "assets/[name].[hash][extname]",
        hashCharacters: "base36",
      },
    },
    reportCompressedSize: false,
    chunkSizeWarningLimit: 8192,
  },
  css: {
    preprocessorOptions: {
      scss: {
        quietDeps: true,
        silenceDeprecations: ["import"],
      },
    },
    postcss: {
      plugins: [autoprefixer()],
    },
  },
  plugins: [
    Macros(),
    legacy({
      modernTargets: browserslist[0],
      modernPolyfills: true,
      renderLegacyChunks: false,
    }),
    {
      name: "serve-rtl-css",
      apply: "serve",
      configureServer(server) {
        server.middlewares.use(async (req, res, next) => {
          const rawUrl = req.originalUrl ?? req.url
          if (!rawUrl) return next()

          const url = new URL(rawUrl, server.config.server.origin)
          if (!CSS_FILE_RE.test(url.pathname)) return next()

          const referer =
            typeof req.headers.referer === "string" ? req.headers.referer : ""
          const hasRtlParam = url.searchParams.has("rtl")
          const scriptRtl =
            url.searchParams.get("rtl") === "1" || referer.includes("rtl=1")

          if (!(scriptRtl || hasRtlParam)) return next()

          const requestPath = `${trimDevBase(server.config.base, url.pathname)}${url.search}`

          if (scriptRtl) {
            const result = await server.transformRequest(requestPath)
            assert(result && typeof result.code === "string")

            const rewritten = rewriteCssModule(result.code, (css) =>
              rtlcss.process(css),
            )

            res.setHeader("Content-Type", "application/javascript")
            res.end(rewritten)
            return
          }

          const params = new URLSearchParams(url.searchParams)
          params.delete("rtl")
          const inlineParts: string[] = []
          for (const [key, value] of params.entries()) {
            inlineParts.push(value ? `${key}=${value}` : key)
          }
          inlineParts.push("inline")
          const inlinePath = `${trimDevBase(server.config.base, url.pathname)}?${inlineParts.join("&")}`

          const mod = await server.ssrLoadModule(inlinePath)
          const css =
            (mod && typeof mod.default === "string" && mod.default) ||
            (mod && typeof mod.css === "string" && mod.css)
          assert(typeof css === "string")

          res.setHeader("Content-Type", "text/css")
          res.end(rtlcss.process(css))
        })
      },
    },
    {
      name: "build-purgecss",
      apply: "build",
      enforce: "post",
      async generateBundle(_options, bundle) {
        const cssEntries = Object.entries(bundle).filter(
          ([fileName, chunk]) => fileName.endsWith(".css") && chunk.type === "asset",
        )
        if (!cssEntries.length) return

        const purgecss = new PurgeCSS()
        await Promise.all(
          cssEntries.map(async ([fileName, chunk]) => {
            if (chunk.type !== "asset") return
            const source =
              typeof chunk.source === "string"
                ? chunk.source
                : Buffer.from(chunk.source).toString()

            const [result] = await purgecss.purge({
              content: CONTENT_PATHS,
              css: [{ raw: source, name: fileName }],
              safelist: PURGECSS_SAFELIST,
              defaultExtractor: PURGECSS_EXTRACTOR,
            })
            if (result) {
              chunk.source = result.css
            }
          }),
        )
      },
    },
    {
      name: "build-rtl-css",
      apply: "build",
      generateBundle(_options, bundle) {
        for (const [fileName, chunk] of Object.entries(bundle)) {
          if (
            !fileName.endsWith(".css") ||
            fileName.includes(".rtl.") ||
            chunk.type !== "asset"
          )
            continue

          const source =
            typeof chunk.source === "string"
              ? chunk.source
              : Buffer.from(chunk.source).toString()

          const rtlSource = rtlcss.process(source)
          const rtlFileName = `${fileName.slice(0, fileName.length - 4)}.rtl.css`

          this.emitFile({
            type: "asset",
            fileName: rtlFileName,
            source: rtlSource,
          })
        }
      },
    },
    {
      name: "build-icons-subset",
      apply: "build",
      enforce: "post",
      generateBundle(_options, bundle) {
        // Scan content files for bi-* icon usage
        const biPattern = /\bbi-([a-z0-9-]+)\b/g
        const usedIcons = new Set<string>()

        for (const pattern of CONTENT_PATHS) {
          for (const file of globSync(pattern)) {
            const content = readFileSync(file, "utf-8")
            for (const match of content.matchAll(biPattern)) {
              usedIcons.add(match[1])
            }
          }
        }

        for (const icon of SOCIALS_ICONS) {
          usedIcons.add(icon.slice(3))
        }

        // Load icon name → unicode mapping
        const iconsMap: Record<string, number> = JSON.parse(
          readFileSync(
            "node_modules/bootstrap-icons/font/bootstrap-icons.json",
            "utf-8",
          ),
        )

        // Warn about unknown icons
        for (const icon of [...usedIcons]) {
          if (!(icon in iconsMap)) {
            this.warn(`Unknown Bootstrap icon: bi-${icon}`)
            usedIcons.delete(icon)
          }
        }

        // Build unicode list
        const unicodes = [...usedIcons]
          .map((icon) => `U+${iconsMap[icon].toString(16).toUpperCase()}`)
          .join(",")

        // Generate subset font
        const inputPath =
          "node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff2"
        const tempFile = join(tmpdir(), `bi-subset-${process.pid}.woff2`)
        execSync(
          `pyftsubset "${inputPath}" --unicodes="${unicodes}" --flavor=woff2 --layout-features=* --no-hinting --desubroutinize --output-file="${tempFile}"`,
          { stdio: "pipe" },
        )
        const source = readFileSync(tempFile)
        rmSync(tempFile)

        const originalSize = statSync(inputPath).size
        const reduction = ((1 - source.length / originalSize) * 100).toFixed(1)
        this.info(
          `Detected ${usedIcons.size} icons, ${originalSize}B → ${source.length}B (${reduction}% smaller)`,
        )

        const ref = this.emitFile({
          type: "asset",
          name: "bootstrap-icons.woff2",
          source,
        })
        const woff2File = this.getFileName(ref)

        // Replace font URLs in CSS
        const fontUrlPattern =
          /\/static\/vite\/assets\/bootstrap-icons\.[a-z0-9]+\.woff2?(?:\?[^")]*)?/g

        for (const [fileName, chunk] of Object.entries(bundle)) {
          if (!fileName.endsWith(".css") || chunk.type !== "asset") continue
          const css =
            typeof chunk.source === "string"
              ? chunk.source
              : Buffer.from(chunk.source).toString()

          chunk.source = css.replace(fontUrlPattern, `/static/vite/${woff2File}`)
        }
      },
    },
    visualizer({
      filename: "app/static/vite/stats.html",
    }) as PluginOption,
  ],
})
