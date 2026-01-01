import {
  getActionSidebar,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { routerNavigateStrict } from "@index/router"
import { isLatitude, isLongitude } from "@lib/coords"
import { newNoteControlActive } from "@lib/map/controls/new-note"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { type LayerId, layersConfig } from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { getMapState, setMapState } from "@lib/map/state"
import { type IdResponse, IdResponseSchema, NoteStatus } from "@lib/proto/shared_pb"
import { qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import { LngLat, type Map as MaplibreMap, Marker } from "maplibre-gl"
import { render } from "preact"
import { useId, useRef } from "preact/hooks"

const NOTES_LAYER_ID = "notes" as LayerId
const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
  "circle-radius": 20,
  "circle-color": THEME_COLOR,
  "circle-opacity": 0.5,
  "circle-stroke-color": THEME_COLOR,
  "circle-stroke-opacity": 1,
  "circle-stroke-width": 2.5,
}

const NewNoteSidebar = ({
  map,
  sidebar,
  active,
}: {
  map: MaplibreMap
  sidebar: HTMLElement
  active: ReadonlySignal<boolean>
}) => {
  const formRef = useRef<HTMLFormElement>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const textId = useId()
  const textHelpId = useId()

  const text = useSignal("")
  const lon = useSignal<number | null>(null)
  const lat = useSignal<number | null>(null)
  const hasText = useComputed(() => text.value.trim().length > 0)

  useSignalEffect(() => {
    if (!active.value) return

    const disposeForm = configureStandardForm<IdResponse>(
      formRef.current,
      (data) => {
        if (!active.peek()) return

        console.debug("NewNote: Created", data.id)
        map.fire("reloadnoteslayer")
        routerNavigateStrict(`/note/${data.id}`)
      },
      {
        protobuf: IdResponseSchema,
        abortSignal: true,
        validationCallback: (formData) => {
          formData.set("lon", lon.peek()!.toString())
          formData.set("lat", lat.peek()!.toString())
          return null
        },
      },
    )

    formRef.current?.reset()
    text.value = ""
    switchActionSidebar(map, sidebar)
    setPageTitle(t("notes.new.title"))
    newNoteControlActive.value = true

    // Allow default location setting via URL search parameters
    let center: LngLat | undefined
    const searchParams = qsParse(window.location.search)
    if (searchParams.lon && searchParams.lat) {
      const lon = Number.parseFloat(searchParams.lon)
      const lat = Number.parseFloat(searchParams.lat)
      if (isLongitude(lon) && isLatitude(lat)) {
        center = new LngLat(lon, lat)
      }
    }

    const marker = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement("new", false),
      draggable: true,
    })
      .setLngLat(center ?? map.getCenter())
      .addTo(map)

    const updateFromMarker = () => {
      const lngLat = marker.getLngLat()

      // Focus halo and update inputs
      focusObjects(
        map,
        [
          {
            type: "note",
            id: null,
            geom: [lngLat.lng, lngLat.lat],
            status: NoteStatus.open,
            text: "",
          },
        ],
        focusPaint,
        null,
        false,
      )

      lon.value = lngLat.lng
      lat.value = lngLat.lat
    }

    marker.on("dragstart", () => focusObjects(map)) // hide halo
    marker.on("dragend", updateFromMarker) // show halo

    // Initial update
    updateFromMarker()
    textRef.current?.focus()

    // Enable notes layer to prevent duplicates
    const state = getMapState(map)
    const notesLayerCode = layersConfig.get(NOTES_LAYER_ID)!.layerCode!
    if (!state.layersCode.includes(notesLayerCode)) {
      state.layersCode += notesLayerCode
      setMapState(map, state)
    }

    return () => {
      disposeForm?.()
      newNoteControlActive.value = false
      focusObjects(map)
      marker.remove()
    }
  })

  return (
    <div class="sidebar-content">
      <form
        ref={formRef}
        class="section"
        method="POST"
        action="/api/web/note"
      >
        <SidebarHeader title={t("notes.new.title")} />

        <p class="mb-2">{t("notes.new.intro")}</p>

        <div class="custom-input-group">
          <label for={textId}>{t("notes.show.description")}</label>
          <textarea
            ref={textRef}
            class="form-control"
            id={textId}
            name="text"
            rows={7}
            required
            aria-describedby={textHelpId}
            onInput={(e) => (text.value = e.currentTarget.value)}
          />
        </div>
        <div
          id={textHelpId}
          class="form-text mb-4"
        >
          {t("notes.new.advice")}
        </div>

        <button
          class="btn btn-primary w-100"
          type="submit"
          disabled={!hasText.value}
        >
          {t("notes.new.add")}
        </button>
      </form>
    </div>
  )
}

export const getNewNoteController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("new-note")
  const active = signal(false)

  render(
    <NewNoteSidebar
      map={map}
      sidebar={sidebar}
      active={active}
    />,
    sidebar,
  )

  return {
    load: () => {
      active.value = true
    },
    unload: () => {
      active.value = false
    },
  }
}
