import { API_URL } from "@lib/config"
import type { LonLatZoom } from "@lib/map/state"
import { qsEncode } from "@lib/qs"
import type { OSMObject } from "@lib/types"
import type { ReadonlySignal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren, Ref } from "preact"

const REMOTE_EDIT_HOST = "http://localhost:8111"

/**
 * Get object request URL
 * @example
 * getObjectRequestUrl({ type: "node", id: 123456n })
 * // => "https://api.openstreetmap.org/api/0.6/node/123456"
 */
const getObjectRequestUrl = (object: OSMObject) => {
  const type = object.type === "note" ? "notes" : object.type

  // When requested for complex object, request for full version (incl. object's members)
  // Ignore version specification as there is a very high chance it will be rendered incorrectly
  if (type === "way" || type === "relation") {
    return `${API_URL}/api/0.6/${type}/${object.id}/full`
  }

  // @ts-expect-error
  const version = object.version
  return version
    ? `${API_URL}/api/0.6/${type}/${object.id}/${version}`
    : `${API_URL}/api/0.6/${type}/${object.id}`
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

const remoteEditOpen = async ({
  state,
  object,
}: {
  state: LonLatZoom
  object: OSMObject | undefined
}) => {
  console.debug("RemoteEdit: Opening", { state, object })
  const [minLon, minLat, maxLon, maxLat] = getBoundsFromCoords(state, 0.05)
  const loadQuery: Record<string, string> = {
    left: minLon.toString(),
    bottom: minLat.toString(),
    right: maxLon.toString(),
    top: maxLat.toString(),
  }

  // Select object if specified
  if (object && object.type !== "note" && object.type !== "changeset") {
    loadQuery.select = `${object.type}${object.id}`
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
    if (object && object.type === "note" && object.id !== null) {
      await fetch(
        `${REMOTE_EDIT_HOST}/import${qsEncode({ url: getObjectRequestUrl(object) })}`,
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
  object,
  onBeforeOpen,
  buttonRef,
  class: className,
  children,
}: {
  state: ReadonlySignal<LonLatZoom>
  object: ReadonlySignal<OSMObject | undefined>
  onBeforeOpen?: () => void
  buttonRef: Ref<HTMLButtonElement>
  class?: string
  children: ComponentChildren
}) => {
  const pending = useSignal(false)

  const onClick = async () => {
    if (pending.value) return
    pending.value = true
    try {
      onBeforeOpen?.()
      await remoteEditOpen({
        state: state.value,
        object: object.value,
      })
    } finally {
      pending.value = false
    }
  }

  return (
    <button
      ref={buttonRef}
      class={className}
      type="button"
      disabled={pending.value}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
