import legacy from "@vitejs/plugin-legacy"
import autoprefixer from "autoprefixer"
import { defineConfig } from "vite"
import { browserslist } from "./package.json"

export default defineConfig({
    server: {
        port: 8000,
        strictPort: true,
        proxy: {
            "^(?!/(@vite|node_modules)/)": {
                target: "http://127.0.0.1:49568",
                changeOrigin: true,
            },
        },
    },
    build: {
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
    optimizeDeps: {
        noDiscovery: true,
    },
    plugins: [
        legacy({
            modernTargets: browserslist[0],
            modernPolyfills: true,
            renderLegacyChunks: false,
        }),
    ],
})
