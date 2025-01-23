type WebAssemblyModule = Omit<typeof import("./wasm/index.js"), "memory">

let loadPromise: Promise<WebAssemblyModule> | null = null
let load = async (): Promise<WebAssemblyModule> => {
    if (window.WebAssembly) {
        if (!loadPromise)
            loadPromise = new Promise((resolve) => {
                import("./wasm/index.js").then((wasm) => {
                    console.debug("Loading WebAssembly module")
                    load = async () => wasm
                    resolve(wasm)
                })
            })
        return await loadPromise
    }
    console.warn("WebAssembly is not supported, falling back to JS implementation")
    const result = {}
    load = async () => result
    return result
}
