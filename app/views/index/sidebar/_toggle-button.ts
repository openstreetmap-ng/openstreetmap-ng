import { rightSidebar } from "@lib/map/main-map"
import { effect } from "@preact/signals"
import { Tooltip } from "bootstrap"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"

export type RightSidebarKind = "layers" | "legend" | "share"

export class SidebarToggleControl implements IControl {
  protected readonly tooltipTitle: string
  private readonly _kind: RightSidebarKind

  public _container!: HTMLElement
  protected tooltip!: Tooltip
  protected button!: HTMLButtonElement
  protected map!: MaplibreMap

  public constructor(kind: RightSidebarKind, tooltipTitle: string) {
    this._kind = kind
    this.tooltipTitle = tooltipTitle
  }

  public onAdd(map: MaplibreMap) {
    this.map = map

    // Create container
    const container = document.createElement("div")
    container.className = `maplibregl-ctrl maplibregl-ctrl-group ${this._kind}`

    // Create button and tooltip
    this.button = document.createElement("button")
    this.button.type = "button"
    this.button.className = "control-btn"
    this.button.ariaLabel = this.tooltipTitle
    const icon = document.createElement("img")
    icon.className = `icon ${this._kind}`
    icon.src = `/static/img/controls/_generated/${this._kind}.webp`
    this.button.append(icon)
    container.append(this.button)

    this.tooltip = new Tooltip(this.button, {
      title: this.tooltipTitle,
      placement: "left",
    })

    effect(() => {
      this.button.classList.toggle("active", rightSidebar.value === this._kind)
    })

    // On click, toggle sidebar visibility
    this.button.addEventListener("click", () => {
      console.debug("SidebarToggle: Button clicked", this._kind)

      this.button.blur()

      rightSidebar.value = rightSidebar.peek() !== this._kind ? this._kind : null
    })

    this._container = container
    return container
  }

  public close = () => {
    if (rightSidebar.peek() === this._kind) rightSidebar.value = null
  }

  public onRemove(_: MaplibreMap) {
    // Do nothing
  }
}
