import { routerRoute } from "@index/router"
import { IndexRouterOutlet } from "@index/router-outlet"
import { SearchForm } from "@index/search-form"
import { RightSidebarOutlet } from "@index/sidebar/sidebar-outlet"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { MapAlerts } from "@lib/map/alerts"
import { initMainMap, mainMap, rightSidebar } from "@lib/map/main-map"
import { qsParseAll } from "@lib/qs"
import { openRemoteEdit, parseRemoteEditTargetFromQueryParams } from "@lib/remote-edit"
import { render } from "preact"
import { useEffect, useRef } from "preact/hooks"
import { collapseNavbar } from "../navbar/navbar"
import { updateNavbarAndHash } from "../navbar/navbar-left"

const IndexApp = () => {
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

    initMainMap(mapContainerRef.current!, updateNavbarAndHash)

    if (remoteEdit) {
      const { lng, lat } = mainMap.value!.getCenter().wrap()
      const zoom = mainMap.value!.getZoom()
      void openRemoteEdit({
        state: { lon: lng, lat, zoom },
        target: remoteEditTarget,
      })
    }
  }, [])

  useDisposeSignalEffect((scope) => {
    // Track route changes + right sidebar open/close
    routerRoute.value
    rightSidebar.value

    collapseNavbar()
    scope.frame(() => mainMap.value!.resize())
  })

  const sidebarOverlay = Boolean(routerRoute.value?.sidebarOverlay)

  return (
    <>
      {mainMap.value && (
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

      {mainMap.value && <RightSidebarOutlet />}
    </>
  )
}

const container = document.getElementById("IndexApp")
if (container) render(<IndexApp />, container)
