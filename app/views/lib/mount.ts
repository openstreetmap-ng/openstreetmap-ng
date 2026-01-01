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
) => {
    const matches =
        typeof target === "string"
            ? bodyClasses.has(target)
            : target.some(bodyClasses.has, bodyClasses)
    if (matches) callback(document.body as HTMLBodyElement)
}
