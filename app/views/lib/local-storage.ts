import { isLatitude, isLongitude, isZoom } from "@lib/coords"
import type { LayerId } from "@lib/map/layers/layers"
import type { MapState } from "@lib/map/state"
import { effect, type Signal, signal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
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
  const storage = createStorage<T>(key, config)
  const storageSignal = signal(storage.get())
  let initialized = false

  effect(() => {
    if (storageSignal.value && initialized) {
      storage.set(storageSignal.value)
    }
    initialized = true
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

export const routingEngineStorage = createStorageSignal<string>("routingEngine", {
  defaultValue: "valhalla_auto",
})

export const globeProjectionStorage = createStorage<boolean>("globeProjection")

export const layerOrderStorage = createStorage<LayerId[]>("layerOrder")

export const overlayOpacityStorage = createScopedStorage<number>("overlayOpacity", {
  defaultValue: 0.55,
  validate: (v) => v >= 0 && v <= 1,
  logOperations: false,
})

export const shareExportFormatStorage = createStorage<string>("shareExportFormat", {
  defaultValue: "image/jpeg",
})

export const tagsDiffStorage = createStorage<boolean>("tagsDiff", {
  defaultValue: true,
})

export const systemAppAccessTokenStorage = createScopedStorage<string>(
  "systemAppAccessToken",
  {
    logOperations: false,
  },
)

export const timezoneUpdateTimeStorage = createStorage<number>("timezoneUpdateTime")
