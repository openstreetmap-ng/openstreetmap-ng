import { useSignal, type Signal } from "@preact/signals"
import type { DataValid } from "@proto/changeset_pb"
import { Service } from "@proto/element_pb"
import { useDisposeSignalEffect } from "@utils/dispose-scope"
import { rpcUnary } from "@utils/rpc"
import { t } from "i18next"
import type { FeatureCollection } from "geojson"
import { LngLatBounds, type GeoJSONSource, type Map as MaplibreMap } from "maplibre-gl"
import { DiffTooLargeError, loadChangesetDiff, MAX_DIFF_ELEMENTS } from "./_changeset-diff"

const SOURCE = "changeset-diff"
const LAYERS = ["changeset-diff-line", "changeset-diff-point"]
const empty: FeatureCollection = { type: "FeatureCollection", features: [] }

export const ChangesetDiffControl = ({
  data,
  map,
  active,
}: {
  data: DataValid
  map: MaplibreMap
  active: Signal<boolean>
}) => {
  const status = useSignal<"idle" | "loading" | "ready" | "error" | "large">("idle")
  const features = useSignal(empty)
  const phase = useSignal("all")
  const retry = useSignal(0)
  useDisposeSignalEffect((scope) => {
    if (!active.value) return
    retry.value
    status.value = "loading"
    void loadChangesetDiff(
      data,
      async (ref, signal) =>
        (await rpcUnary(Service.method.get)({ ref: { case: "version", value: ref } }, { signal }))
          .element,
      scope.signal,
    )
      .then((result) => {
        if (scope.signal.aborted) return
        const bounds = new LngLatBounds()
        for (const feature of result.features) {
          const geometry = feature.geometry
          if (geometry.type === "Point") bounds.extend(geometry.coordinates as [number, number])
          else if (geometry.type === "LineString")
            for (const point of geometry.coordinates) bounds.extend(point as [number, number])
        }
        if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 35, maxZoom: 18, duration: 0 })
        features.value = result
        status.value = "ready"
      })
      .catch((error) => {
        if (!scope.signal.aborted)
          status.value = error instanceof DiffTooLargeError ? "large" : "error"
      })
  })
  useDisposeSignalEffect((scope) => {
    if (!active.value) return
    const selected = phase.value
    const collection = status.value === "ready" ? features.value : empty
    const filtered: FeatureCollection = {
      type: "FeatureCollection",
      features: collection.features.filter(
        (f) => selected === "all" || f.properties?.phase === selected,
      ),
    }
    const draw = () => {
      if (!map.getSource(SOURCE)) map.addSource(SOURCE, { type: "geojson", data: filtered })
      else map.getSource<GeoJSONSource>(SOURCE)!.setData(filtered)
      if (!map.getLayer(LAYERS[0]!))
        map.addLayer({
          id: LAYERS[0]!,
          type: "line",
          source: SOURCE,
          filter: ["==", ["geometry-type"], "LineString"],
          paint: {
            "line-color": ["match", ["get", "phase"], "before", "#c23632", "#16834a"],
            "line-width": 4,
          },
        })
      if (!map.getLayer(LAYERS[1]!))
        map.addLayer({
          id: LAYERS[1]!,
          type: "circle",
          source: SOURCE,
          filter: ["==", ["geometry-type"], "Point"],
          paint: {
            "circle-color": ["match", ["get", "phase"], "before", "#c23632", "#16834a"],
            "circle-radius": ["match", ["get", "phase"], "before", 9, 6],
            "circle-stroke-width": 1,
            "circle-stroke-color": "#ffffff",
          },
        })
    }
    if (map.isStyleLoaded()) draw()
    scope.map(map, "style.load", draw)
    scope.defer(() => {
      for (const id of LAYERS) if (map.getLayer(id)) map.removeLayer(id)
      if (map.getSource(SOURCE)) map.removeSource(SOURCE)
    })
  })
  return (
    <div class="my-3">
      <button
        type="button"
        class="btn btn-sm btn-outline-primary"
        aria-pressed={active.value}
        onClick={() => {
          active.value = !active.value
        }}
      >
        <i class={`bi ${active.value ? "bi-x-lg" : "bi-intersect"} me-2`} />
        {t(active.value ? "changeset_diff.close" : "changeset_diff.open")}
      </button>
      {active.value && (
        <>
          <div
            class="btn-group btn-group-sm d-flex mt-2"
            role="group"
            aria-label={t("changeset_diff.view")}
          >
            {["all", "before", "after"].map((value) => (
              <button
                key={value}
                type="button"
                class={`btn btn-outline-secondary ${phase.value === value ? "active" : ""}`}
                aria-pressed={phase.value === value}
                onClick={() => {
                  phase.value = value
                }}
              >
                {t(`changeset_diff.${value}`)}
              </button>
            ))}
          </div>
          <div
            class="small mt-2"
            role="status"
          >
            {status.value === "loading" && t("browse.start_rjs.loading")}
            {status.value === "large" && t("changeset_diff.large", { count: MAX_DIFF_ELEMENTS })}
            {status.value === "error" && (
              <>
                {t("changeset_diff.error")}{" "}
                <button
                  type="button"
                  class="btn btn-link btn-sm p-0"
                  onClick={() => {
                    retry.value++
                  }}
                >
                  {t("changeset_diff.retry")}
                </button>
              </>
            )}
            {status.value === "ready" && (
              <span>
                <span class="text-danger">{t("changeset_diff.before")}</span>
                {" / "}
                <span class="text-success">{t("changeset_diff.after")}</span>
                {!features.value.features.length && ` · ${t("changeset_diff.empty")}`}
              </span>
            )}
            {!!data.relations.length && (
              <p class="text-muted mb-0">
                {t("changeset_diff.relations", { count: data.relations.length })}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
