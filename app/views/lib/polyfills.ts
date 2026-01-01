import { SECOND } from "@std/datetime/constants"

// Enable JSON.stringify for BigInt
// @ts-expect-error - extending built-in prototype
BigInt.prototype.toJSON = function () {
    return this.toString()
}

export const requestAnimationFramePolyfill: (callback: FrameRequestCallback) => number =
    window.requestAnimationFrame ||
    ((callback) => window.setTimeout(() => callback(performance.now()), 30))

export const requestIdleCallbackPolyfill: (
    callback: IdleRequestCallback,
    options?: IdleRequestOptions,
) => number =
    window.requestIdleCallback ||
    ((callback) =>
        window.setTimeout(
            () => callback({ didTimeout: false, timeRemaining: () => 0 }),
            0,
        ))

export const cancelIdleCallbackPolyfill: (handle: number) => void =
    window.cancelIdleCallback || window.clearTimeout

/** Wrap a low-priority function to execute during idle time */
export const wrapIdleCallbackStatic = <T extends (...args: never[]) => void>(
    fn: T,
    timeout = 5 * SECOND,
) => {
    let idleCallbackId: number | undefined
    return ((...args) => {
        if (idleCallbackId !== undefined) cancelIdleCallbackPolyfill(idleCallbackId)
        idleCallbackId = requestIdleCallbackPolyfill(() => fn(...args), { timeout })
    }) as T
}
