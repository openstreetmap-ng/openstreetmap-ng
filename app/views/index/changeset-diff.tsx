import { LoadingSpinner } from "@index/_action-sidebar"
import { clearChangesetDiff, setChangesetDiff } from "@map/layers/changeset-diff"
import { convertRenderElementsData } from "@map/render-objects"
import { useSignal } from "@preact/signals"
import { Service as ChangesetService } from "@proto/changeset_pb"
import { rpcUnary } from "@utils/rpc"
import type { OSMNode, OSMWay } from "@utils/osm-objects"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { useEffect } from "preact/hooks"

type DiffObjects = (OSMNode | OSMWay)[]

type DiffState =
  | { tag: "loading" }
  | {
      tag: "ready"
      compared: number
      truncated: number
      contextTruncated: boolean
      before: DiffObjects
      after: DiffObjects
    }
  | { tag: "error" }

const loadDiff = async (
  changesetId: bigint,
  signal: AbortSignal,
): Promise<Extract<DiffState, { tag: "ready" }>> => {
  const response = await rpcUnary(ChangesetService.method.getDiff)(
    { id: changesetId },
    { signal },
  )
  return {
    tag: "ready",
    compared: response.numElements,
    truncated: response.numTruncated,
    contextTruncated: response.contextTruncated,
    before: convertRenderElementsData(response.before),
    after: convertRenderElementsData(response.after),
  }
}

const DiffLegend = () => (
  <div class="changeset-diff-legend small mb-2">
    <span>
      <i
        class="changeset-diff-swatch changeset-diff-swatch-before me-1"
        aria-hidden="true"
      />
      {t("changeset.diff.before")}
    </span>
    <span class="ms-3">
      <i
        class="changeset-diff-swatch changeset-diff-swatch-after me-1"
        aria-hidden="true"
      />
      {t("changeset.diff.after")}
    </span>
  </div>
)

export const ChangesetDiff = ({
  map,
  data,
}: {
  map: MaplibreMap
  data: { id: bigint }
}) => {
  const state = useSignal<DiffState>({ tag: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    clearChangesetDiff(map)
    state.value = { tag: "loading" }

    void loadDiff(data.id, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setChangesetDiff(map, result.before, result.after)
        state.value = result
      })
      .catch((error) => {
        if (controller.signal.aborted) return
        console.error("ChangesetDiff: Failed to load", error)
        state.value = { tag: "error" }
      })

    return () => {
      controller.abort()
      clearChangesetDiff(map)
    }
  }, [map, data])

  const current = state.value
  return (
    <div
      class="section changeset-diff"
      aria-live="polite"
    >
      <h4>{t("changeset.diff.title")}</h4>
      {current.tag === "loading" ? (
        <div class="d-flex align-items-center gap-2 text-muted">
          <LoadingSpinner />
          <span>{t("changeset.diff.loading")}</span>
        </div>
      ) : current.tag === "error" ? (
        <p class="alert alert-warning mb-0">{t("changeset.diff.error")}</p>
      ) : (
        <>
          <DiffLegend />
          <p class="small text-muted mb-1">
            {t("changeset.diff.summary", { count: current.compared })}
          </p>
          {!current.before.length && !current.after.length && (
            <p class="small text-muted mb-1">{t("changeset.diff.no_geometry")}</p>
          )}
          {current.truncated > 0 && (
            <p class="small text-muted mb-1">
              {t("changeset.diff.limit", { count: current.truncated })}
            </p>
          )}
          {current.contextTruncated && (
            <p class="small text-muted mb-0">{t("changeset.diff.context_limit")}</p>
          )}
        </>
      )}
    </div>
  )
}
