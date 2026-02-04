import { routerParams, routerQuery, routerRoute } from "@index/router"
import { mainMap } from "@lib/map/main-map"
import type { RefObject } from "preact"

export const IndexRouterOutlet = ({
  sidebarRef,
}: {
  sidebarRef: RefObject<HTMLElement>
}) => {
  const route = routerRoute.value!
  return (
    <div class={`action-sidebar ${route.id}`}>
      <route.Component
        key={route.id}
        map={mainMap.value!}
        sidebarRef={sidebarRef}
        {...routerParams.value}
        {...routerQuery.value}
      />
    </div>
  )
}
