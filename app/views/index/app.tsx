import { routerRoute } from "@index/router"
import { IndexRouterOutlet } from "@index/router-outlet"
import { SearchForm } from "@index/search-form"
import { RightSidebarOutlet } from "@index/sidebar/sidebar-outlet"
import { useDisposeLayoutEffect } from "@lib/dispose-scope"
import { MapAlertPanel, MapAlerts, pushMapAlert } from "@lib/map/alerts"
import { initMainMap, mainMap, rightSidebar } from "@lib/map/main-map"
import { qsParseAll } from "@lib/qs"
import { openRemoteEdit, parseRemoteEditTargetFromQueryParams } from "@lib/remote-edit"
import { render } from "preact"
import { useEffect, useRef } from "preact/hooks"
import { collapseNavbar } from "../navbar/navbar"
import { updateNavbarAndHash } from "../navbar/navbar-left"

const IndexPage = () => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const sidebarRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const searchParams = qsParseAll(location.search)
    const remoteEdit =
      location.pathname === "/edit" && searchParams.editor?.at(-1) === "remote"
    const remoteEditTarget = remoteEdit
      ? parseRemoteEditTargetFromQueryParams(searchParams)
      : null

    if (remoteEdit) {
      // Normalize the URL before bootstrapping the index router.
      // `/edit` is a real server endpoint; the index router must not own it.
      const pathname = remoteEditTarget
        ? `/${remoteEditTarget.type}/${remoteEditTarget.id}`
        : "/"
      window.history.replaceState(null, "", `${pathname}${location.hash}`)
    }

    initMainMap(mapContainerRef.current!, updateNavbarAndHash, ({ heading, details }) =>
      pushMapAlert(
        <MapAlertPanel variant="danger">
          <h4 class="alert-heading">{heading}</h4>
          {details && <pre class="mb-0">{details}</pre>}
        </MapAlertPanel>,
      ),
    )
    const map = mainMap.value
    if (!map) return

    if (remoteEdit) {
      const { lng, lat } = map.getCenter().wrap()
      const zoom = map.getZoom()
      void openRemoteEdit({
        state: { lon: lng, lat, zoom },
        target: remoteEditTarget,
      })
    }
  }, [])

  const map = mainMap.value
  const route = routerRoute.value
  const sidebarKind = rightSidebar.value

  useDisposeLayoutEffect(() => {
    collapseNavbar()
    map?.resize()
  }, [map, route, sidebarKind])

  const sidebarOverlay = Boolean(route?.sidebarOverlay)

  return (
    <>
      {map && (
        <div
          class={`sidebar ${sidebarOverlay ? "sidebar-overlay" : ""}`}
          ref={sidebarRef}
        >
          <SearchForm />
          <IndexRouterOutlet sidebarRef={sidebarRef} />
        </div>
      )}

      <div
        class="main-map"
        ref={mapContainerRef}
      >
        <MapAlerts />
      </div>

      {map && <RightSidebarOutlet />}
    </>
  )
}

const container = document.getElementById("IndexRoot")
if (container) render(<IndexPage />, container)
