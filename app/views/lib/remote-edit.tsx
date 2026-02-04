import { routerRemoteEditTarget } from "@index/router"
import { routeParam } from "@lib/codecs"
import { API_URL } from "@lib/config"
import type { LonLatZoom } from "@lib/map/state"
import { qsEncode } from "@lib/qs"
import type { ReadonlySignal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren } from "preact"

const REMOTE_EDIT_HOST = "http://localhost:8111"

export type RemoteEditTarget = Readonly<{
  type: "node" | "way" | "relation" | "note"
  id: bigint
}>

export const parseRemoteEditTargetFromQueryParams = (
  queryParams: Record<string, string[]>,
): RemoteEditTarget | null => {
  const idSchema = routeParam.positive()
  for (const type of ["node", "way", "relation", "note"] as const) {
    const raw = queryParams[type]?.at(-1)
    if (!raw) continue
    const parsed = idSchema.safeDecode(raw)
    if (!parsed.success) continue
    return { type, id: parsed.data }
  }
  return null
}

const getBoundsFromCoords = ({ lon, lat, zoom }: LonLatZoom, paddingRatio = 0) => {
  // Assume the map takes up the entire screen
  const mapHeight = window.innerHeight
  const mapWidth = window.innerWidth

  const tileSize = 256
  const tileCountHalfX = mapWidth / tileSize / 2
  const tileCountHalfY = mapHeight / tileSize / 2

  const n = 2 ** zoom
  const deltaLon = (tileCountHalfX / n) * 360 * (1 + paddingRatio)
  const deltaLat = (tileCountHalfY / n) * 180 * (1 + paddingRatio)

  return [lon - deltaLon, lat - deltaLat, lon + deltaLon, lat + deltaLat]
}

export const openRemoteEdit = async ({
  state,
  target,
}: {
  state: LonLatZoom
  target: RemoteEditTarget | null
}) => {
  console.debug("RemoteEdit: Opening", { state, target })
  const [minLon, minLat, maxLon, maxLat] = getBoundsFromCoords(state, 0.05)
  const loadQuery: Record<string, string> = {
    left: minLon.toString(),
    bottom: minLat.toString(),
    right: maxLon.toString(),
    top: maxLat.toString(),
  }

  // Select object if specified
  if (target && target.type !== "note") {
    loadQuery.select = `${target.type}${target.id}`
  }

  try {
    await fetch(`${REMOTE_EDIT_HOST}/load_and_zoom${qsEncode(loadQuery)}`, {
      method: "GET",
      mode: "no-cors",
      credentials: "omit",
      cache: "no-store",
      priority: "high",
    })

    // Optionally import note
    if (target?.type === "note") {
      await fetch(
        `${REMOTE_EDIT_HOST}/import${qsEncode({
          url: `${API_URL}/api/0.6/notes/${target.id}`,
        })}`,
        {
          method: "GET",
          mode: "no-cors",
          credentials: "omit",
          cache: "no-store",
          priority: "high",
        },
      )
    }
  } catch (error) {
    console.error("RemoteEdit: Failed", error)
    alert(t("site.index.remote_failed"))
  }
}

export const RemoteEditButton = ({
  state,
  onBeforeOpen,
  class: className,
  children,
}: {
  state: ReadonlySignal<LonLatZoom>
  onBeforeOpen?: () => void
  class?: string
  children: ComponentChildren
}) => {
  const pending = useSignal(false)

  const onClick = async () => {
    if (pending.value) return
    pending.value = true
    try {
      onBeforeOpen?.()
      await openRemoteEdit({
        state: state.value,
        target: routerRemoteEditTarget.value,
      })
    } finally {
      pending.value = false
    }
  }

  return (
    <button
      class={className}
      type="button"
      disabled={pending.value}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
