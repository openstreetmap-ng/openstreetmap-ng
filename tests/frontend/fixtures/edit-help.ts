import { signal } from "@preact/signals"
import { render } from "preact"
export const editDisabled = signal(new URLSearchParams(location.search).has("disabled"))
export const currentHash = signal(location.hash),
  currentMapState = signal({})
export const isLoggedIn = !new URLSearchParams(location.search).has("loggedOut")
export const preferredEditorStorage = signal("id")
export const qsEncode = (p: Record<string, string>) => "?" + new URLSearchParams(p)
export const assertNever = () => {
  throw Error("never")
}
export const RemoteEditButton = () => null
export const t = (key: string) =>
  key === "javascripts.edit_help"
    ? "Move the map and zoom in on a location you want to edit, then click here."
    : key
Object.assign(window, { editDisabled })

export const addMapLayer = () => {},
  removeMapLayer = () => {}
Object.assign(window, {
  unmount: () => render(null, document.getElementById("NavbarLeft")!),
})

export const assert = (value: unknown, message?: string) => {
  if (!value) throw new Error(message)
}
export const mapNotNullish = (items: unknown[], fn: (value: unknown) => unknown) =>
  items.map(fn).filter((value) => value !== null && value !== undefined)
export const sumOf = <T>(values: T[], fn: (value: T) => number) =>
  values.reduce((sum, value) => sum + fn(value), 0)
export const trimEndBy = (value: string, suffix: string) => {
  while (value.endsWith(suffix)) value = value.slice(0, -suffix.length)
  return value
}
export const getPathParamSpecificity = () => 1
export const isUnmodifiedLeftClick = (event: MouseEvent) =>
  !event.defaultPrevented &&
  event.button === 0 &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey
