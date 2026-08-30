import {
  openRemoteEdit,
  parseRemoteEditTargetFromQueryParams,
} from "@index/remote-edit"
import { routerRoute } from "@index/router"
import { IndexRouterOutlet } from "@index/router-outlet"
import { SearchForm } from "@index/search-form"
import { RightSidebarOutlet } from "@index/sidebar"
import { MapAlertPanel, MapAlerts, pushMapAlert } from "@map/alerts"
import { initMainMap, mainMap, rightSidebar } from "@map/main-map"
import { preferredEditorStorage } from "@utils/local-storage"
import { useDisposeLayoutEffect } from "@utils/dispose-scope"
import { qsEncode, qsParseAll } from "@utils/query-string"
import { t } from "i18next"
import { render } from "preact"
import { useEffect, useRef } from "preact/hooks"
import { collapseNavbar } from "../navbar/navbar"
import { currentHash, editDisabled, updateNavbarAndHash } from "../navbar/navbar-left-state"

const buildEditHelpHref = () =>
  `/edit${qsEncode({ editor: preferredEditorStorage.value })}${currentHash.value}`

const EditHelpAlert = ({ onDismiss }: { onDismiss: () => void }) => (
  <MapAlertPanel variant="info">
    <div class="d-flex justify-content-between align-items-start gap-3">
      <div>
        <p class="mb-3">{t("javascripts.site.edit_help")}</p>
        <a
          class={`btn btn-primary ${editDisabled.value ? "disabled" : ""}`}
          href={editDisabled.value ? undefined : buildEditHelpHref()}
          aria-disabled={editDisabled.value}
          tabIndex={editDisabled.value ? -1 : undefined}
        >
          {t("layouts.edit")}
        </a>
      </div>
      <button
        class="btn-close flex-shrink-0"
        type="button"
        aria-label={t("javascripts.close")}
        onClick={onDismiss}
      />
    </div>
  </MapAlertPanel>
)

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

    const showEditHelp = searchParams.edit_help?.at(-1) === "1"
    const removeEditHelpAlert = showEditHelp
      ? pushMapAlert(<EditHelpAlert onDismiss={() => removeEditHelpAlert()} />)
      : null

    if (remoteEdit) {
      const { lng, lat } = map.getCenter().wrap()
      const zoom = map.getZoom()
      void openRemoteEdit({
        state: { lon: lng, lat, zoom },
        target: remoteEditTarget,
      })
    }

    return () => {
      removeEditHelpAlert?.()
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
