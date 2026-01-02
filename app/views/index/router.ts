import { unquotePlus } from "@lib/utils"
import { batch, computed, effect, signal } from "@preact/signals"
import { assert } from "@std/assert"
import { trimEndBy } from "@std/text/unstable-trim-by"

export type RouteLoadReason = "navigation" | "popstate"

export interface IndexController {
  load: (matchGroups: Record<string, string>, reason?: RouteLoadReason) => void
  unload: (newPath?: string) => void
}

interface Route {
  match: (path: string) => boolean
  load: (path: string, reason: RouteLoadReason) => void
  unload: (newPath?: string) => void
}

let routes: Route[]
let loadReason: RouteLoadReason
const currentPath = signal<string>("")
const currentRoute = computed(() => {
  const p = currentPath.value
  return p ? routes.find((r) => r.match(p)) : null
})

const removeTrailingSlash = (s: string) => trimEndBy(s, "/") || "/"

const getCurrentPath = () =>
  unquotePlus(removeTrailingSlash(window.location.pathname) + window.location.search)

export const makeRoute = (pattern: string, controller: IndexController): Route => {
  const re = new RegExp(`^${pattern}(?:$|\\?)`)
  return {
    match: re.test.bind(re),
    load: (path, reason) => controller.load(re.exec(path)!.groups ?? {}, reason),
    unload: controller.unload,
  }
}

export const routerNavigate = (newPath: string) => {
  console.debug("Router: Navigate", newPath)
  if (!routes.some((r) => r.match(newPath))) return false

  history.pushState(null, "", newPath + location.hash)
  loadReason = "navigation"
  currentPath.value = newPath
  return true
}

export const routerNavigateStrict = (newPath: string) => {
  console.debug("Router: Navigate strict", newPath)
  assert(routerNavigate(newPath), `No route found for path: ${newPath}`)
}

export const configureRouter = (pathControllerMap: Map<string, IndexController>) => {
  routes = Array.from(pathControllerMap, ([p, c]) => makeRoute(p, c))
  console.debug("Router: Loaded routes", routes.length)

  // Browser navigation
  window.addEventListener("popstate", () => {
    console.debug("Router: Browser navigation", location)
    const path = getCurrentPath()
    if (path === currentPath.value) return

    loadReason = "popstate"
    currentPath.value = path
  })

  // Anchor click interception
  window.addEventListener("click", (e) => {
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

    const path = removeTrailingSlash(target.pathname) + target.search
    console.debug("Router: Anchor click", path)
    if (routerNavigate(path)) e.preventDefault()
  })

  // Effect: route lifecycle
  let prevPath = currentPath.value
  let prevRoute = currentRoute.value
  loadReason = "navigation"
  currentPath.value = getCurrentPath()
  effect(() => {
    const path = currentPath.value
    if (path === prevPath) return

    batch(() => {
      const route = currentRoute.value
      prevRoute?.unload(path)
      prevPath = path
      prevRoute = route
      route?.load(path, loadReason)
    })
  })
}
