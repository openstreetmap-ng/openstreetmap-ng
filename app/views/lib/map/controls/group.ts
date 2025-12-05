import type { IControl, Map as MaplibreMap } from "maplibre-gl"

/** Add a control group to the map */
export const addControlGroup = (map: MaplibreMap, controls: IControl[]) => {
    for (const [i, control] of controls.entries()) {
        map.addControl(control)

        // @ts-expect-error
        const container: HTMLElement | undefined = control._container
        if (!container) continue
        const classList = container.classList
        classList.add("custom-control-group")

        if (i === 0) classList.add("first")
        if (i === controls.length - 1) classList.add("last")
    }
}
