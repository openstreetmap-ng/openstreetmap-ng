import { unquotePlus } from "../lib/utils"

// Router interfaces
export interface IndexController {
    load: (matchGroups: { [key: string]: string }) => void
    unload: (newPath?: string) => void
}

export interface Route {
    match: (path: string) => boolean
    load: (path: string) => void
    unload: (newPath?: string) => void
}

// Router state
let routes: Route[] | null = null
let currentPath: string | null = null
let currentRoute: Route | null = null

/**
 * Remove trailing slash from a string
 * @example
 * removeTrailingSlash("/way/1234/")
 * // => "/way/1234"
 */
const removeTrailingSlash = (str: string): string =>
    str.endsWith("/") && str.length > 1 ? removeTrailingSlash(str.slice(0, -1)) : str

/** Find the first route that matches a path */
const findRoute = (path: string): Route | undefined =>
    routes.find((route) => route.match(path))

/** Create a route object */
export const makeRoute = (pattern: string, controller: IndexController): Route => {
    // Ignore query string and require exact match
    const re = new RegExp(`^${pattern}($|\\?)`)

    return {
        /** Test if a path matches this route */
        match: (path: string): boolean => re.test(path),

        /** Execute load action on this route */
        load: (path: string): void => {
            // Extract path parameters
            const matchGroups = re.exec(path).groups
            controller.load(matchGroups)
        },

        /** Execute unload action on this route */
        unload: controller.unload,
    }
}

/**
 * Navigate to a path, throwing an error if no route is found
 * @example
 * routerNavigateStrict("/way/1234")
 */
export const routerNavigateStrict = (newPath: string): void => {
    console.debug("routerNavigateStrict", newPath)
    if (!routerNavigate(newPath)) throw new Error(`No route found for path: ${newPath}`)
}

/**
 * Navigate to a path and return true if successful
 * @example
 * routerNavigate("/way/1234")
 * // => true
 */
export const routerNavigate = (newPath: string): boolean => {
    console.debug("routerNavigate", newPath)
    const newRoute = findRoute(newPath)
    if (!newRoute) return false

    // Unload the current route
    currentRoute?.unload(newPath)

    // Push the new history state
    history.pushState(null, "", newPath + location.hash)

    // Load the new route
    currentPath = newPath
    currentRoute = newRoute
    currentRoute.load(currentPath)
    return true
}

/** Configure the router */
export const configureRouter = (
    pathControllerMap: Map<string, IndexController>,
): void => {
    routes = Array.from(pathControllerMap).map(([path, controller]) =>
        makeRoute(path, controller),
    )
    console.debug("Loaded", routes.length, "application routes")

    const getCurrentPath = (): string =>
        unquotePlus(
            removeTrailingSlash(window.location.pathname) + window.location.search,
        )

    currentPath = getCurrentPath()
    currentRoute = findRoute(currentPath)

    window.addEventListener("popstate", (): void => {
        console.debug("onBrowserNavigation", location)
        const newPath = getCurrentPath()

        // Skip if the path hasn't changed
        if (newPath === currentPath) return

        const newRoute = findRoute(newPath)

        // Unload the current route
        currentRoute?.unload(newPath)

        // Load the new route
        currentPath = newPath
        currentRoute = newRoute
        currentRoute?.load(currentPath)
    })

    // On window click, attempt to navigate to the href of an anchor element
    window.addEventListener("click", (e: MouseEvent): void => {
        // Skip if default prevented
        if (e.defaultPrevented) return

        // Skip if not left click or modified click
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return

        // Skip if target is not an anchor
        const target = (e.target as Element).closest("a")
        if (!target) return

        // Skip if the anchor is not a link
        if (!target.href) return

        // Skip if cross-protocol or cross-origin
        if (location.protocol !== target.protocol || location.host !== target.host)
            return

        // Attempt to navigate and prevent default if successful
        const newPath = removeTrailingSlash(target.pathname) + target.search
        console.debug("onWindowClick", newPath)

        if (routerNavigate(newPath)) {
            e.preventDefault()
        }
    })

    // Initial load
    currentRoute?.load(currentPath)
}
