/**
 * Throttle a function to only be called at most once per delay
 * @example
 * throttle(() => console.log("Hello"), 1000)
 */
export const throttle = <T extends any[]>(
    func: (...args: T) => void,
    delay: number,
): ((...args: T) => void) => {
    let lastCalled = 0
    let timeout: ReturnType<typeof setTimeout> | null = null

    return (...args) => {
        clearTimeout(timeout)
        const now = performance.now()
        const timeElapsed = now - lastCalled
        const timeLeft = delay - timeElapsed

        if (timeLeft <= 0) {
            lastCalled = now
            func(...args)
        } else {
            timeout = setTimeout(() => {
                lastCalled = performance.now()
                func(...args)
            }, timeLeft)
        }
    }
}
