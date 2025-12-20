import { unquotePlus } from "@lib/utils"
import { assert } from "@std/assert"
import { trimEndBy } from "@std/text/unstable-trim-by"

// Router interfaces
export type RouteLoadReason = "navigation" | "popstate"

export interface IndexController {
    load: (matchGroups: Record<string, string>, reason?: RouteLoadReason) => void
    unload: (newPath?: string) => void
}

export interface Route {
    match: (path: string) => boolean
    load: (path: string, reason: RouteLoadReason) => void
    unload: (newPath?: string) => void
}

// Router state
let routes: Route[] = []
let currentPath: string | undefined
let currentRoute: Route | null = null

const findRoute = (p: string) => routes.find((r) => r.match(p)) ?? null

export const makeRoute = (pattern: string, controller: IndexController) => {
    const re = new RegExp(`^${pattern}(?:$|\\?)`) // match pattern, allow query string

    return {
        match: (path: string) => re.test(path),
        load: (path: string, reason: RouteLoadReason) => {
            const matchGroups = re.exec(path)!.groups ?? {}
            controller.load(matchGroups, reason)
        },
        unload: controller.unload,
    }
}

const removeTrailingSlash = (s: string) => trimEndBy(s, "/") || "/"

export const routerNavigate = (newPath: string) => {
    console.debug("Router: Navigate", newPath)
    const newRoute = findRoute(newPath)
    if (!newRoute) return false

    // Ensure unload hooks fire before history change
    currentRoute?.unload(newPath)
    history.pushState(null, "", newPath + location.hash)
    currentPath = newPath
    currentRoute = newRoute
    currentRoute.load(currentPath, "navigation")
    return true
}

export const routerNavigateStrict = (newPath: string) => {
    console.debug("Router: Navigate strict", newPath)
    assert(routerNavigate(newPath), `No route found for path: ${newPath}`)
}

export const configureRouter = (pathControllerMap: Map<string, IndexController>) => {
    routes = Array.from(pathControllerMap, ([p, c]) => makeRoute(p, c))
    console.debug("Router: Loaded routes", routes.length)

    const getCurrentPath = () =>
        unquotePlus(
            removeTrailingSlash(window.location.pathname) + window.location.search,
        )

    // Handle browser back/forward navigation
    window.addEventListener("popstate", () => {
        console.debug("Router: Browser navigation", location)
        const newPath = getCurrentPath()
        if (newPath === currentPath) return

        // Ensure unload hooks fire before state change
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
        if (!target?.href || target.origin !== location.origin) return

        const newPath = removeTrailingSlash(target.pathname) + target.search
        console.debug("Router: Anchor click", newPath)
        if (routerNavigate(newPath)) e.preventDefault()
    })

    // Initial load
    currentPath = getCurrentPath()
    currentRoute = findRoute(currentPath)
    currentRoute?.load(currentPath, "navigation")
}
