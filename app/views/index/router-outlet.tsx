import { type AnyRouteDef, routerParams, routerQuery, routerRoute } from "@index/router"
import { useSignalEffect } from "@preact/signals"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { ComponentChildren } from "preact"
import { collapseNavbar } from "../navbar/navbar"

const RouteRenderer = ({ map, route }: { map: MaplibreMap; route: AnyRouteDef }) => {
  const RouteComponent = route.Component
  return (
    <RouteComponent
      map={map}
      {...routerParams.value}
      {...routerQuery.value}
    />
  )
}

export const IndexRouterOutlet = ({ map }: { map: MaplibreMap }): ComponentChildren => {
  // Effect: apply route-level shell state (classes/overlay) on route changes.
  useSignalEffect(() => {
    const route = routerRoute.value
    if (!route) return

    const sidebar = document.getElementById("ActionSidebar")!.closest("div.sidebar")!
    sidebar.classList.toggle("sidebar-overlay", Boolean(route.sidebarOverlay))

    map.resize()
    collapseNavbar()
  })

  const route = routerRoute.value
  if (!route) return null

  return (
    <div class={`action-sidebar ${route.id}`}>
      <RouteRenderer
        key={route.id}
        map={map}
        route={route}
      />
    </div>
  )
}
