import { dirname, relative } from "node:path"
import { fileURLToPath } from "node:url"
import legacy from "@vitejs/plugin-legacy"
import autoprefixer from "autoprefixer"
import rtlcss from "rtlcss"
import { defineConfig } from "vite"
import { browserslist } from "./package.json"

const getPackageDist = (pkgName: string): string => {
    const absolutePath = dirname(fileURLToPath(import.meta.resolve(pkgName)))
    const relativePath = relative(process.cwd(), absolutePath).replace(/\\/g, "/")
    return `${relativePath}/`
}

export default defineConfig({
    appType: "custom",
    base: "/static/vite/",
    clearScreen: false,
    server: {
        host: "127.0.0.1",
        port: 49568,
        strictPort: true,
        origin: "http://127.0.0.1:49568",
    },
    define: {
        __ID_PATH__: JSON.stringify(`/static-${getPackageDist("iD")}`),
        __RAPID_PATH__: JSON.stringify(
            `/static-${getPackageDist("@rapideditor/rapid")}`,
        ),
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
                    const url = new URL(
                        `http://${process.env.HOST ?? "localhost"}${req.url}`,
                    )
                    if (!url.searchParams.has("rtl")) return next()

                    const modPath = `/${url.pathname.slice(server.config.base.length)}?${url.searchParams.toString()}&inline`
                    const mod = await server.ssrLoadModule(modPath)
                    const css =
                        (typeof mod.default === "string" && mod.default) ||
                        (typeof mod.css === "string" && mod.css)
                    if (!css) return next()

                    res.setHeader("Content-Type", "text/css")
                    res.end(rtlcss.process(css))
                })
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
    ],
})
