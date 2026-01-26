import { SidebarHeader } from "@index/_action-sidebar"
import { NoteRoute } from "@index/note"
import { defineRoute, routerNavigate } from "@index/router"
import { queryParam } from "@lib/codecs"
import { useDisposeEffect } from "@lib/dispose-scope"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { addMapLayer, hasMapLayer, NOTES_LAYER_ID } from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { type LonLatZoom, lonLatZoomEquals } from "@lib/map/state"
import { NoteStatus } from "@lib/proto/note_pb"
import { type IdResponse, IdResponseSchema } from "@lib/proto/shared_pb"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import { type Signal, useSignal, useSignalEffect } from "@preact/signals"
import { t } from "i18next"
import { type LngLat, type Map as MaplibreMap, Marker } from "maplibre-gl"
import { useId, useRef } from "preact/hooks"

export const NEW_NOTE_MIN_ZOOM = 12

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
  at,
}: {
  map: MaplibreMap
  at: Signal<LonLatZoom | undefined>
}) => {
  setPageTitle(t("notes.new.title"))

  const formRef = useRef<HTMLFormElement>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const textId = useId()
  const textHelpId = useId()

  const markerRef = useRef<Marker | null>(null)
  const text = useSignal("")

  const setAt = ({ lng, lat }: LngLat) => {
    at.value = { lon: lng, lat, zoom: map.getZoom() }
  }

  const focusAt = (lngLat: LngLat) => {
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
  }

  useDisposeEffect((scope) => {
    // Enable notes layer to prevent duplicates
    if (!hasMapLayer(map, NOTES_LAYER_ID)) {
      addMapLayer(map, NOTES_LAYER_ID)
    }

    const disposeForm = configureStandardForm<IdResponse>(
      formRef.current!,
      (data) => {
        console.debug("NewNote: Created", data.id)
        map.fire("reloadnoteslayer")
        routerNavigate(NoteRoute, { id: data.id })
      },
      {
        protobuf: IdResponseSchema,
        validationCallback: (formData) => {
          const { lon, lat } = at.peek()!
          formData.set("lon", lon.toString())
          formData.set("lat", lat.toString())
          return null
        },
      },
    )
    scope.defer(disposeForm)
    textRef.current!.focus()

    const marker = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement("new", false),
      draggable: true,
    })
      .setLngLat(at.peek() ?? map.getCenter())
      .addTo(map)
    markerRef.current = marker

    marker.on("dragstart", () => focusObjects(map)) // hide halo
    marker.on("dragend", () => setAt(marker.getLngLat()))

    scope.map(
      map,
      "moveend",
      () => map.getBounds().contains(marker.getLngLat()) || setAt(map.getCenter()),
    )

    scope.defer(() => {
      focusObjects(map)
      marker.remove()
      markerRef.current = null
    })
  }, [])

  // Effect: URL -> marker (back/forward, manual URL edits, link navigation).
  useSignalEffect(() => {
    const marker = markerRef.current!
    let lngLat = marker.getLngLat()

    const next = at.value
    if (!next) {
      setAt(lngLat)
      return
    }

    const prev = { lon: lngLat.lng, lat: lngLat.lat, zoom: next.zoom }
    const shouldMove = !lonLatZoomEquals(prev, next)
    if (shouldMove) {
      marker.setLngLat(next)
      lngLat = marker.getLngLat()
    }
    focusAt(lngLat)

    const shouldFocus = !map.getBounds().contains(lngLat)
    if (shouldFocus) {
      map.jumpTo({ center: lngLat, zoom: next.zoom })
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
          disabled={text.value.trim().length === 0}
        >
          {t("notes.new.add")}
        </button>
      </form>
    </div>
  )
}

export const NewNoteRoute = defineRoute({
  id: "new-note",
  path: "/note/new",
  query: { at: queryParam.lonLatZoom() },
  Component: NewNoteSidebar,
})
