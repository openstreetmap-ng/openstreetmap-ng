export const requestAnimationFramePolyfill: (callback: FrameRequestCallback) => number =
    window.requestAnimationFrame ||
    ((callback) => window.setTimeout(() => callback(performance.now()), 30))

export const requestIdleCallbackPolyfill: (
    callback: IdleRequestCallback,
    options?: IdleRequestOptions,
) => number =
    window.requestIdleCallback ||
    ((callback) => window.setTimeout(() => callback(null), 0))

export const cancelIdleCallbackPolyfill: (handle: number) => void =
    window.cancelIdleCallback || ((handle) => window.clearTimeout(handle))

export const getDeviceThemePreference = () =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
