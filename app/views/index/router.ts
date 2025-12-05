import { unquotePlus } from "@lib/utils"

// Router interfaces
export type RouteLoadReason = "navigation" | "popstate"

export interface IndexController {
    load: (matchGroups: { [key: string]: string }, reason?: RouteLoadReason) => void
    unload: (newPath?: string) => void
}

export interface Route {
    match: (path: string) => boolean
    load: (path: string, reason: RouteLoadReason) => void
    unload: (newPath?: string) => void
}

// Router state
let routes: Route[] = []
let currentPath: string | null = null
let currentRoute: Route | null = null

/** Find the first route that matches a path */
const findRoute = (p: string) => routes.find((r) => r.match(p)) ?? null

/** Create a route object */
export const makeRoute = (pattern: string, controller: IndexController) => {
    // Ignore query string and require exact match
    const re = new RegExp(`^${pattern}($|\\?)`)

    return {
        /** Test if a path matches this route */
        match: (path: string) => re.test(path),

        /** Execute load action on this route */
        load: (path: string, reason: RouteLoadReason) => {
            // Extract path parameters
            const matchGroups = re.exec(path).groups
            controller.load(matchGroups, reason)
        },

        /** Execute unload action on this route */
        unload: controller.unload,
    }
}

/** Remove trailing slashes from a string, preserving the root "/" */
const removeTrailingSlash = (s: string) => {
    let end = s.length
    while (end > 1 && s[end - 1] === "/") end--
    return end < s.length ? s.slice(0, end) : s
}

/**
 * Navigate to a path and return true if successful
 * @example
 * routerNavigate("/way/1234")
 * // => true
 */
export const routerNavigate = (newPath: string) => {
    console.debug("routerNavigate", newPath)
    const newRoute = findRoute(newPath)
    if (!newRoute) return false

    // Unload current route before changing URL
    currentRoute?.unload(newPath)
    history.pushState(null, "", newPath + location.hash)
    currentPath = newPath
    currentRoute = newRoute
    currentRoute.load(currentPath, "navigation")
    return true
}

/**
 * Navigate to a path, throwing an error if no route is found
 * @example
 * routerNavigateStrict("/way/1234")
 */
export const routerNavigateStrict = (newPath: string) => {
    console.debug("routerNavigateStrict", newPath)
    if (!routerNavigate(newPath)) throw new Error(`No route found for path: ${newPath}`)
}

/** Configure the router */
export const configureRouter = (pathControllerMap: Map<string, IndexController>) => {
    routes = Array.from(pathControllerMap, ([p, c]) => makeRoute(p, c))
    console.debug("Loaded", routes.length, "application routes")

    const getCurrentPath = () =>
        unquotePlus(
            removeTrailingSlash(window.location.pathname) + window.location.search,
        )

    // Sync with browser back/forward navigation
    window.addEventListener("popstate", () => {
        console.debug("onBrowserNavigation", location)
        const newPath = getCurrentPath()
        if (newPath === currentPath) return

        // Unload current route before changing URL
        currentRoute?.unload(newPath)
        currentPath = newPath
        currentRoute = findRoute(newPath)
        currentRoute?.load(currentPath, "popstate")
    })

    // Intercept same-origin anchor clicks to route internally
    window.addEventListener("click", (e: MouseEvent) => {
        if (
            e.defaultPrevented ||
            e.button !== 0 ||
            e.metaKey ||
            e.ctrlKey ||
            e.shiftKey ||
            e.altKey
        )
            return

        const target = (e.target as Element).closest("a")
        if (!target || !target.href || target.origin !== location.origin) return

        const newPath = removeTrailingSlash(target.pathname) + target.search
        console.debug("onWindowClick", newPath)
        if (routerNavigate(newPath)) e.preventDefault()
    })

    // Initial load
    currentPath = getCurrentPath()
    currentRoute = findRoute(currentPath)
    currentRoute?.load(currentPath, "navigation")
}
