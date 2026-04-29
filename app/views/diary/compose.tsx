import {
  config,
  DIARY_BODY_MAX_LENGTH,
  DIARY_TITLE_MAX_LENGTH,
  primaryLanguage,
} from "@lib/config"
import { tryParseLonLat, zoomPrecision } from "@lib/coords"
import { useDisposeEffect, useDisposeLayoutEffect } from "@lib/dispose-scope"
import { getLocaleDisplayName, LOCALE_OPTIONS } from "@lib/locale"
import { configureMap } from "@lib/map/configure-map"
import { CustomGeolocateControl } from "@lib/map/controls/geolocate"
import { addControlGroup } from "@lib/map/controls/group"
import { CustomZoomControl } from "@lib/map/controls/zoom"
import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
  addMapLayer,
  addMapLayerSources,
  DEFAULT_LAYER_ID,
} from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { getInitialMapState, type LonLatZoom } from "@lib/map/state"
import { mountProtoPage } from "@lib/proto-page"
import { ComposePageSchema, Service } from "@lib/proto/diary_pb"
import { StandardForm } from "@lib/standard-form"
import { useSignal } from "@preact/signals"
import { assertExists } from "@std/assert"
import { throttle } from "@std/async/unstable-throttle"
import { t } from "i18next"
import type { LngLat, LngLatLike } from "maplibre-gl"
import { Map as MaplibreMap, Marker } from "maplibre-gl"
import { useRef } from "preact/hooks"
import { RichTextControl } from "../rich-text/_control"

mountProtoPage(ComposePageSchema, ({ diaryId, title, body, language, location }) => {
  const isNew = diaryId === undefined
  const diaryPath = `/user/${config.userConfig!.user.displayName}/diary`
  const selectedLanguage = language ?? primaryLanguage
  const lonInputRef = useRef<HTMLInputElement>(null)
  const latInputRef = useRef<HTMLInputElement>(null)
  const mapDivRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MaplibreMap>(null)
  const markerRef = useRef<Marker>(null)
  const mapVisible = useSignal(location !== undefined)

  const updateLocationValidity = () => {
    const hasLon = lonInputRef.current!.value !== ""
    const hasLat = latInputRef.current!.value !== ""
    const message =
      hasLon !== hasLat ? t("validation.incomplete_location_information") : ""

    lonInputRef.current!.setCustomValidity(hasLat ? "" : message)
    latInputRef.current!.setCustomValidity(hasLon ? "" : message)
  }

  const setMarker = (lngLat: LngLatLike) => {
    if (markerRef.current) {
      markerRef.current.setLngLat(lngLat)
      return
    }

    assertExists(mapRef.current)
    markerRef.current = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement("red", true),
      draggable: true,
    })
      .setLngLat(lngLat)
      .addTo(mapRef.current)
    markerRef.current.on(
      "drag",
      throttle(
        () => {
          if (markerRef.current) setInput(markerRef.current.getLngLat())
        },
        100,
        { ensureLastCall: true },
      ),
    )
  }

  const setInput = (lngLat: LngLat) => {
    assertExists(mapRef.current)
    const precision = zoomPrecision(mapRef.current.getZoom())
    const wrapped = lngLat.wrap()
    lonInputRef.current!.value = wrapped.lng.toFixed(precision)
    latInputRef.current!.value = wrapped.lat.toFixed(precision)
  }

  const onMapClick = ({ lngLat }: { lngLat: LngLat }) => {
    setMarker(lngLat)
    setInput(lngLat)
  }

  const getInputLocation = () => {
    const location = tryParseLonLat(
      lonInputRef.current!.value,
      latInputRef.current!.value,
    )
    return location ? { lon: location[0], lat: location[1] } : null
  }

  const ensureMap = () => {
    if (mapRef.current) return mapRef.current

    const map = configureMap({
      container: mapDivRef.current!,
      maxZoom: 19,
      attributionControl: { compact: true, customAttribution: "" },
      refreshExpiredTiles: false,
    })
    if (!map) return null

    configureDefaultMapBehavior(map)
    addMapLayerSources(map, DEFAULT_LAYER_ID)
    addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
    addMapLayer(map, DEFAULT_LAYER_ID)
    mapRef.current = map
    return map
  }

  const showMap = () => {
    mapVisible.value = true
  }

  const hideMap = () => {
    mapVisible.value = false
    lonInputRef.current!.value = ""
    latInputRef.current!.value = ""
    markerRef.current?.remove()
    markerRef.current = null
  }

  const onCoordinatesInputChange = () => {
    updateLocationValidity()
    if (!mapVisible.value || !mapRef.current) return

    const location = getInputLocation()
    if (location) {
      const lngLat: LngLatLike = [location.lon, location.lat]
      setMarker(lngLat)
      if (!mapRef.current.getBounds().contains(lngLat)) {
        mapRef.current.panTo(lngLat)
      }
    }
  }

  useDisposeLayoutEffect(
    (scope) => {
      if (!mapVisible.value) return

      const map = ensureMap()
      if (!map) return

      map.resize()

      let state: LonLatZoom | undefined
      const location = getInputLocation()
      if (location) {
        state = { ...location, zoom: 10 }
        setMarker([location.lon, location.lat])
      }

      state ??= getInitialMapState(map)
      map.jumpTo({ center: [state.lon, state.lat], zoom: state.zoom })
      scope.map(map, "click", onMapClick)
    },
    [mapVisible.value],
  )

  useDisposeEffect((scope) => {
    const lonInput = lonInputRef.current!
    const latInput = latInputRef.current!

    scope.dom(lonInput, "change", onCoordinatesInputChange)
    scope.dom(latInput, "change", onCoordinatesInputChange)
    updateLocationValidity()

    scope.defer(() => {
      mapRef.current?.remove()
      mapRef.current = null
      markerRef.current = null
    })
  }, [])

  return (
    <>
      <div class="content-header">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{isNew ? t("diary.new_entry") : t("diary_entries.edit.title")}</h1>
          <p class="mb-2">{t("diary.compose.description")}</p>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <StandardForm
            method={Service.method.createOrUpdate}
            buildRequest={({ formData }) => ({
              diaryId,
              title: formData.get("title") as string,
              body: formData.get("body") as string,
              language: formData.get("language") as string,
              location:
                formData.get("lon") && formData.get("lat")
                  ? {
                      lon: Number(formData.get("lon")),
                      lat: Number(formData.get("lat")),
                    }
                  : undefined,
            })}
            onSuccess={({ id }, ctx) => ctx.redirect(`${diaryPath}/${id}`)}
            class="diary-form"
          >
            <label class="form-label d-block mb-3">
              <span class="required">{t("diary.compose.title")}</span>
              <input
                type="text"
                name="title"
                class="form-control mt-2"
                placeholder={t("diary.compose.title_placeholder")}
                defaultValue={title}
                maxLength={DIARY_TITLE_MAX_LENGTH}
                required
              />
            </label>

            <label class="form-label d-block">
              <span class="required">{t("messages.compose.body")}</span>
            </label>
            <RichTextControl
              name="body"
              value={body}
              maxLength={DIARY_BODY_MAX_LENGTH}
              required
            />

            <label class="form-label d-block mt-3">
              {t("activerecord.attributes.diary_entry.language_code")}
              <select
                class="form-select format-select mt-2"
                name="language"
                defaultValue={selectedLanguage}
                required
              >
                {LOCALE_OPTIONS.map((locale) => (
                  <option value={locale[0]}>
                    {getLocaleDisplayName(locale, true)}
                  </option>
                ))}
              </select>
            </label>
            <p class="form-text">{t("diary.compose.language_hint")}</p>

            <h5>{t("diary_entries.form.location")}</h5>
            <div class="show-map-container">
              <div class="row g-3 mb-3">
                <div class="col-md">
                  <label class="form-label d-block mb-0">
                    {t("activerecord.attributes.diary_entry.latitude")}
                    <input
                      ref={latInputRef}
                      type="number"
                      class="form-control mt-2"
                      name="lat"
                      min="-85"
                      max="85"
                      step="any"
                      defaultValue={location?.lat ?? ""}
                    />
                  </label>
                </div>
                <div class="col-md">
                  <label class="form-label d-block mb-0">
                    {t("activerecord.attributes.diary_entry.longitude")}
                    <input
                      ref={lonInputRef}
                      type="number"
                      class="form-control mt-2"
                      name="lon"
                      min="-180"
                      max="180"
                      step="any"
                      defaultValue={location?.lon ?? ""}
                    />
                  </label>
                </div>
                <div class="col-md-auto align-content-end text-end">
                  {mapVisible.value ? (
                    <button
                      class="btn btn-soft px-3"
                      type="button"
                      onClick={hideMap}
                    >
                      {t("diary.compose.remove_location")}
                    </button>
                  ) : (
                    <button
                      class="btn btn-outline-primary px-3"
                      type="button"
                      onClick={showMap}
                    >
                      {t("diary.compose.select_on_map")}
                    </button>
                  )}
                </div>
              </div>
              <div
                ref={mapDivRef}
                class="map-container mb-4"
                hidden={!mapVisible.value}
              />
            </div>

            <div>
              <button
                class={`btn ${isNew ? "btn-lg" : ""} btn-primary px-3`}
                type="submit"
              >
                {isNew
                  ? t("helpers.submit.diary_entry.create")
                  : t("action.save_changes")}
              </button>
            </div>
          </StandardForm>

          {!isNew && diaryId && (
            <>
              <hr class="my-4" />

              <h3 class="mb-3">{t("settings.danger_zone")}</h3>
              <StandardForm
                method={Service.method.delete}
                buildRequest={() => ({ diaryId })}
                onSuccess={(_, ctx) => ctx.redirect(diaryPath)}
                class="delete-form"
              >
                <button
                  class="btn btn-outline-danger"
                  type="submit"
                  onClick={(e) => {
                    if (!confirm(t("diary.delete_confirmation"))) {
                      e.preventDefault()
                    }
                  }}
                >
                  {t("diary.delete_diary_entry")}
                </button>
              </StandardForm>
            </>
          )}
        </div>
      </div>
    </>
  )
})
