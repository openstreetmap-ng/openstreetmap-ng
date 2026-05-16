import { mainMap } from "@map/main-map"
import { encodeMapState, getInitialMapState, type MapState } from "@map/state"
import { computed, signal } from "@preact/signals"

const MIN_EDIT_ZOOM = 13

export const currentMapState = signal(getInitialMapState())

export const currentHash = computed(() =>
  mainMap.value ? encodeMapState(currentMapState.value) : "",
)

export const editDisabled = computed(() =>
  mainMap.value ? currentMapState.value.zoom < MIN_EDIT_ZOOM : false,
)

export const updateNavbarAndHash = (state: MapState) => {
  const hash = encodeMapState(state)
  window.history.replaceState(null, "", hash)
  currentMapState.value = state
}
