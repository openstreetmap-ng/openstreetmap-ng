import { isLatitude, isLongitude, isZoom } from "@lib/coords"
import type { LayerId } from "@lib/map/layers/layers"
import type { MapState } from "@lib/map/state"
import { effect, type Signal, signal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import type { GetRouteRequest_Engine } from "./proto/routing_pb"
import type { Theme } from "./theme"

type StorageConfig<T> = {
  defaultValue?: T
  deserialize?: (value: string) => T
  serialize?: (value: T) => string
  validate?: (value: T) => boolean
  logOperations?: boolean
}

function createStorage<T>(
  key: string,
  config: StorageConfig<T> & { defaultValue: T },
): { get: () => T; set: (value: T) => void }
function createStorage<T>(
  key: string,
  config?: StorageConfig<T>,
): { get: () => T | null; set: (value: T) => void }
function createStorage<T>(key: string, config: StorageConfig<T> = {}) {
  const {
    defaultValue = null,
    deserialize = JSON.parse,
    serialize = JSON.stringify,
    validate,
    logOperations = true,
  } = config

  return {
    get: () => {
      const stored = localStorage.getItem(key)
      if (stored === null) return defaultValue

      try {
        const parsed = deserialize(stored)
        return !validate || validate(parsed) ? parsed : defaultValue
      } catch {
        return defaultValue
      }
    },

    set: (value: T) => {
      if (logOperations) console.debug("LocalStorage: Set", key, "=", value)
      localStorage.setItem(key, serialize(value))
    },
  }
}

function createScopedStorage<T>(
  prefix: string,
  config: StorageConfig<T> & { defaultValue: T },
): (scope: string) => { get: () => T; set: (value: T) => void }
function createScopedStorage<T>(
  prefix: string,
  config?: StorageConfig<T>,
): (scope: string) => { get: () => T | null; set: (value: T) => void }
function createScopedStorage<T>(prefix: string, config?: StorageConfig<T>) {
  return memoize((scope: string) => createStorage<T>(`${prefix}-${scope}`, config))
}

export function createStorageSignal<T>(
  key: string,
  config: StorageConfig<T> & { defaultValue: T },
): Signal<T>
export function createStorageSignal<T>(
  key: string,
  config?: StorageConfig<T>,
): Signal<T | null>
export function createStorageSignal<T>(key: string, config: StorageConfig<T> = {}) {
  let skipUpdates = false
  window.addEventListener("storage", (event) => {
    if (event.storageArea !== localStorage) return
    if (event.key !== key && event.key !== null) return

    skipUpdates = true
    storageSignal.value = storage.get()
    skipUpdates = false
  })

  const storage = createStorage<T>(key, config)
  const storageSignal = signal(storage.get())

  let initialized = false
  effect(() => {
    const value = storageSignal.value

    if (skipUpdates) return
    if (!initialized) {
      initialized = true
      return
    }

    if (value === null) localStorage.removeItem(key)
    else storage.set(value)
  })

  return storageSignal
}

function createScopedStorageSignal<T>(
  prefix: string,
  config: StorageConfig<T> & { defaultValue: T },
): (scope: string) => Signal<T>
function createScopedStorageSignal<T>(
  prefix: string,
  config?: StorageConfig<T>,
): (scope: string) => Signal<T | null>
function createScopedStorageSignal<T>(prefix: string, config?: StorageConfig<T>) {
  return memoize((scope: string) =>
    createStorageSignal<T>(`${prefix}-${scope}`, config),
  )
}

export const themeStorage = createStorageSignal<Theme>("theme", {
  defaultValue: "auto",
})

export const mapStateStorage = createStorage<MapState>("mapState", {
  validate: (value) =>
    isLongitude(value.lon) && isLatitude(value.lat) && isZoom(value.zoom),
  logOperations: false,
})

export const bannerHidden = createScopedStorageSignal<boolean>("bannerHidden", {
  defaultValue: false,
})

export type RoutingEngineKey = keyof typeof GetRouteRequest_Engine

export const ROUTING_ENGINE_KEYS = [
  "graphhopper_car",
  "osrm_car",
  "valhalla_auto",
  "graphhopper_bike",
  "osrm_bike",
  "valhalla_bicycle",
  "graphhopper_foot",
  "osrm_foot",
  "valhalla_pedestrian",
] as const satisfies readonly RoutingEngineKey[]

export const routingEngineStorage = createStorageSignal<RoutingEngineKey>(
  "routingEngine",
  {
    defaultValue: "valhalla_auto",
    validate: (value) => ROUTING_ENGINE_KEYS.includes(value),
  },
)

export const globeProjectionStorage = createStorageSignal<boolean>("globeProjection", {
  defaultValue: false,
})

export const layerOrderStorage = createStorageSignal<LayerId[]>("layerOrder", {
  defaultValue: [],
})

export const overlayOpacityStorage = createScopedStorageSignal<number>(
  "overlayOpacity",
  {
    defaultValue: 0.55,
    validate: (v) => v >= 0 && v <= 1,
    logOperations: false,
  },
)

export const shareExportFormatStorage = createStorageSignal<string>(
  "shareExportFormat",
  {
    defaultValue: "image/jpeg",
  },
)

export const tagsDiffStorage = createStorageSignal<boolean>("tagsDiff", {
  defaultValue: true,
})

const EDITOR_KEYS = ["id", "rapid", "remote"] as const

export type Editor = (typeof EDITOR_KEYS)[number]

export const preferredEditorStorage = createStorageSignal<Editor>("preferredEditor", {
  defaultValue: "id",
  validate: (value) => EDITOR_KEYS.includes(value),
})

export const systemAppAccessTokenStorage = createScopedStorage<string>(
  "systemAppAccessToken",
  {
    logOperations: false,
  },
)

export const timezoneUpdateTimeStorage = createStorage<number>("timezoneUpdateTime")
