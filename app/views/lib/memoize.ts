import { cancelIdleCallbackPolyfill, requestIdleCallbackPolyfill } from "@lib/polyfills"

export const memoize = <T extends (...args: any[]) => any>(fn: T) => {
    let noArgsCalled = false
    let noArgsResult: ReturnType<T> | undefined
    const cache = new Map<string, ReturnType<T>>()

    return ((...args: Parameters<T>) => {
        // Fast path for zero-argument calls
        if (args.length === 0) {
            if (noArgsCalled) return noArgsResult
            noArgsResult = fn()
            noArgsCalled = true
            return noArgsResult
        }

        // Standard path for calls with arguments
        const key = JSON.stringify(args)
        if (cache.has(key)) return cache.get(key)!
        const result = fn(...args)
        cache.set(key, result)
        return result
    }) as T
}

/** Wrap a low-priority function to execute during idle time */
export const wrapIdleCallbackStatic = <T extends (...args: any[]) => any>(
    fn: T,
    timeout = 5000,
) => {
    let idleCallbackId: number | undefined
    return ((...args: any[]) => {
        if (idleCallbackId !== undefined) cancelIdleCallbackPolyfill(idleCallbackId)
        idleCallbackId = requestIdleCallbackPolyfill(() => fn(...args), { timeout })
    }) as T
}
