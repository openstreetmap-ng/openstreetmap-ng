import assert from "node:assert/strict"
import { fileURLToPath } from "node:url"
import legacy from "@vitejs/plugin-legacy"
import autoprefixer from "autoprefixer"
import { PurgeCSS } from "purgecss"
import { visualizer } from "rollup-plugin-visualizer"
import rtlcss from "rtlcss"
import Macros from "unplugin-macros/vite"
import { defineConfig, type PluginOption } from "vite"
import { browserslist } from "./package.json"

const CSS_FILE_RE = /\.(?:c|s[ac])ss$/i

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
        // Bootstrap icons from config/socials.toml
        "bi-bluesky",
        "bi-discord",
        "bi-facebook",
        "bi-github",
        "bi-globe2", // other.icon
        "bi-instagram",
        "bi-line",
        "bi-linkedin",
        "bi-mastodon",
        "bi-medium",
        "bi-pinterest",
        "bi-reddit",
        "bi-signal",
        "bi-sina-weibo",
        "bi-snapchat",
        "bi-spotify",
        "bi-steam",
        "bi-telegram",
        "bi-threads",
        "bi-tiktok",
        "bi-twitch",
        "bi-twitter-x", // x.icon
        "bi-wechat",
        "bi-whatsapp",
        "bi-wordpress",
        "bi-youtube",
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
                replacement: fileURLToPath(
                    import.meta.resolve("bootstrap/js/index.esm.js"),
                ),
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
                        typeof req.headers.referer === "string"
                            ? req.headers.referer
                            : ""
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
                    ([fileName, chunk]) =>
                        fileName.endsWith(".css") && chunk.type === "asset",
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
                            content: ["app/views/**/*.html.jinja", "app/views/**/*.ts"],
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
        visualizer({
            filename: "app/static/vite/stats.html",
        }) as PluginOption,
    ],
})
