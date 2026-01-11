import { type ReadonlySignal, type Signal, signal } from "@preact/signals"
import { assertExists } from "@std/assert"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"

let activeControl: SidebarToggleControl | null = null

export class SidebarToggleControl implements IControl {
  protected sidebar!: HTMLElement
  protected tooltip!: Tooltip
  protected button!: HTMLButtonElement
  protected map!: MaplibreMap
  private readonly _active: Signal<boolean> = signal(false)
  public readonly active: ReadonlySignal<boolean> = this._active
  private readonly _className: string
  private readonly _tooltipTitle: string

  public constructor(className: string, tooltipTitle: string) {
    this._className = className
    this._tooltipTitle = tooltipTitle
  }

  private _ensureSidebar = () => {
    const existing = document.querySelector(`div.map-sidebar.${this._className}`)
    assertExists(existing, `Sidebar ${this._className} not found`)
    return existing
  }

  private setActive = (nextActive: boolean, resize = true) => {
    if (this._active.peek() === nextActive) return

    this._active.value = nextActive
    this.button.classList.toggle("active", nextActive)
    this.sidebar.hidden = !nextActive

    if (nextActive) {
      activeControl = this
    } else if (activeControl === this) {
      activeControl = null
    }

    if (resize) this.map.resize()
  }

  public onAdd(map: MaplibreMap) {
    this.map = map

    // Find corresponding sidebar
    this.sidebar = this._ensureSidebar()

    // Create container
    const container = document.createElement("div")
    container.className = `maplibregl-ctrl maplibregl-ctrl-group ${this._className}`

    // Create button and tooltip
    const buttonText = t(this._tooltipTitle)
    this.button = document.createElement("button")
    this.button.type = "button"
    this.button.className = "control-btn"
    this.button.ariaLabel = buttonText
    const icon = document.createElement("img")
    icon.className = `icon ${this._className}`
    icon.src = `/static/img/controls/_generated/${this._className}.webp`
    this.button.appendChild(icon)
    container.appendChild(this.button)

    // noinspection ObjectAllocationIgnored
    this.tooltip = new Tooltip(this.button, {
      title: buttonText,
      placement: "left",
    })

    // On click, toggle sidebar visibility and invalidate map size
    this.button.addEventListener("click", () => {
      console.debug("SidebarToggle: Button clicked", this._className)

      const nextActive = !this._active.peek()
      const prevActiveControl = activeControl
      const isSwitch =
        nextActive && prevActiveControl !== null && prevActiveControl !== this

      if (isSwitch) prevActiveControl.setActive(false, false)

      // Lose focus
      this.button.blur()

      this.setActive(nextActive, !isSwitch)
    })

    return container
  }

  public close = () => {
    this.setActive(false)
  }

  public onRemove(_: MaplibreMap) {
    // Do nothing
  }
}
