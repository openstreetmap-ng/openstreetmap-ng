class AssertionError extends Error {
    override name = "AssertionError"
}

/**
 * Asserts that a value is not null or undefined, narrowing the type.
 * Use for edge cases that shouldn't happen but theoretically could.
 * Backend responses and templates are guaranteed correct - use `!` for those.
 */
export function assert<T>(value: T, message?: string): asserts value is NonNullable<T> {
    if (value === null || value === undefined)
        throw new AssertionError(message ?? "null or undefined")
}
