const bodyClasses = new Set(document.body.classList)

/**
 * Run a feature initializer only when the `<body>` carries the expected class.
 *
 * Pass one class name or a list of names that identify the page markup this
 * module needs. If any match the body, the callback receives the `<body>`
 * element so it can mount UI or start event bindings.
 */
export const mount = (
    target: string | readonly string[],
    callback: (body: HTMLBodyElement) => void | Promise<void>,
): void => {
    const matches = Array.isArray(target)
        ? target.some((className) => bodyClasses.has(className))
        : bodyClasses.has(target as string)
    if (matches) callback(document.body as HTMLBodyElement)
}
