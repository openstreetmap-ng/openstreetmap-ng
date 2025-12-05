import { cancelIdleCallbackPolyfill, requestIdleCallbackPolyfill } from "@lib/polyfills"

/** Memoize a function result, depending on the arguments */
export const memoize = <T extends (...args: any[]) => any>(fn: T): T => {
    let noArgsCalled = false
    let noArgsResult: ReturnType<T> | undefined
    const cache = new Map<string, ReturnType<T>>()

    return ((...args: Parameters<T>): ReturnType<T> => {
        // Fast path for zero-argument calls
        if (args.length === 0) {
            if (noArgsCalled) return noArgsResult
            noArgsCalled = true
            noArgsResult = fn()
            return noArgsResult
        }

        // Standard path for calls with arguments
        const key = JSON.stringify(args)
        let cached = cache.get(key)
        if (cached === undefined) {
            cached = fn(...args)
            cache.set(key, cached)
        }
        return cached
    }) as T
}

/** Wrap a low-priority function to execute during idle time */
export const wrapIdleCallbackStatic = <T extends (...args: any[]) => any>(
    fn: T,
    timeout = 5000,
): T => {
    let idleCallbackId: number | null = null
    return ((...args: any[]) => {
        cancelIdleCallbackPolyfill(idleCallbackId)
        idleCallbackId = requestIdleCallbackPolyfill(() => fn(...args), { timeout })
    }) as T
}
