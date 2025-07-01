import type { GeoJSON } from "geojson"
import {
    type GeoJSONSource,
    type IControl,
    LngLatBounds,
    type Map as MaplibreMap,
    Marker,
} from "maplibre-gl"
import type { Bounds } from "../../types"
import { mod, throttle } from "../../utils"
import {
    addMapLayer,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "../layers/layers"

const layerId: LayerId = "location-filter" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["fill"],
    layerOptions: {
        paint: {
            "fill-color": "black",
            "fill-opacity": 0.3,
            "fill-outline-color": "transparent",
        },
    },
})

export class LocationFilterControl implements IControl {
    private _map: MaplibreMap
    private _bounds: Bounds
    private _grabber: Marker
    private _corners: Marker[]
    private _onRenderHandlers: (() => void)[] = []

    public addTo(map: MaplibreMap, bounds: LngLatBounds): this {
        this._map = map
        addMapLayer(map, layerId)

        const [[minLon, minLat], [maxLon, maxLat]] = bounds.toArray()
        this._bounds = [minLon, minLat, maxLon, maxLat]

        this._grabber = new Marker({
            anchor: "top-left",
            element: createGrabberElement(),
            draggable: true,
        })
            .setLngLat([minLon, maxLat])
            .addTo(map)
        this._grabber.on(
            "drag",
            throttle(() => this._processMarkerUpdate(-1), 16),
        )
        this._corners = []
        for (const [i, x, y] of [
            [0, minLon, minLat],
            [1, minLon, maxLat],
            [2, maxLon, maxLat],
            [3, maxLon, minLat],
        ]) {
            const corner = new Marker({
                anchor: "center",
                element: createCornerElement(),
                draggable: true,
            })
                .setLngLat([x, y])
                .addTo(map)
            corner.on(
                "drag",
                throttle(() => this._processMarkerUpdate(i), 16),
            )
            this._corners.push(corner)
        }

        this._render()
        return this
    }

    public remove(): void {
        removeMapLayer(this._map, layerId)
        for (const corner of this._corners) corner.remove()
        this._corners = null
        this._grabber.remove()
        this._grabber = null
    }

    public getBounds(): LngLatBounds {
        let [minLon, minLat, maxLon, maxLat] = this._bounds
        if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon]
        if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat]
        return new LngLatBounds([minLon, minLat, maxLon, maxLat])
    }

    private _processMarkerUpdate(i: number) {
        let [minLon, minLat, maxLon, maxLat] = this._bounds
        if (i === -1) {
            const lngLat = this._grabber.getLngLat()

            // Update longitude bounds
            const deltaX = lngLat.lng - Math.min(minLon, maxLon)
            maxLon += deltaX
            minLon += deltaX

            // Update latitude bounds
            const nextTop = this._map.project(lngLat)
            if (minLat > maxLat) {
                const prevTop = this._map.project([lngLat.lng, minLat])
                const bottom = this._map.project([lngLat.lng, maxLat])
                bottom.y += nextTop.y - prevTop.y
                minLat = lngLat.lat
                maxLat = this._map.unproject(bottom).lat
            } else {
                const prevTop = this._map.project([lngLat.lng, maxLat])
                const bottom = this._map.project([lngLat.lng, minLat])
                bottom.y += nextTop.y - prevTop.y
                minLat = this._map.unproject(bottom).lat
                maxLat = lngLat.lat
            }
        } else if (i === 0) {
            const lngLat = this._corners[0].getLngLat()
            minLon = lngLat.lng
            minLat = lngLat.lat
        } else if (i === 1) {
            const lngLat = this._corners[1].getLngLat()
            minLon = lngLat.lng
            maxLat = lngLat.lat
        } else if (i === 2) {
            const lngLat = this._corners[2].getLngLat()
            maxLon = lngLat.lng
            maxLat = lngLat.lat
        } else if (i === 3) {
            const lngLat = this._corners[3].getLngLat()
            maxLon = lngLat.lng
            minLat = lngLat.lat
        } else {
            console.warn("Invalid marker index", i)
            return
        }
        if (minLat < -85) minLat = -85
        else if (minLat > 85) minLat = 85
        if (maxLat < -85) maxLat = -85
        else if (maxLat > 85) maxLat = 85
        this._bounds = [minLon, minLat, maxLon, maxLat]
        this._render(i)
    }

    private _render(i?: number): void {
        const [minLon, minLat, maxLon, maxLat] = this._bounds
        if (i !== -1)
            this._grabber.setLngLat([
                Math.min(minLon, maxLon),
                Math.max(minLat, maxLat),
            ])
        if (i !== 0) this._corners[0].setLngLat([minLon, minLat])
        if (i !== 1) this._corners[1].setLngLat([minLon, maxLat])
        if (i !== 2) this._corners[2].setLngLat([maxLon, maxLat])
        if (i !== 3) this._corners[3].setLngLat([maxLon, minLat])
        const source = this._map.getSource(layerId) as GeoJSONSource
        source.setData(getMaskData(this._bounds))
        for (const handler of this._onRenderHandlers) handler()
    }

    public addOnRenderHandler(handler: () => void): void {
        this._onRenderHandlers.push(handler)
    }

    public onAdd(_: MaplibreMap): HTMLElement {
        // Do nothing
        return
    }

    public onRemove(): void {
        // Do nothing
    }
}

const createGrabberElement = (): HTMLElement => {
    const container = document.createElement("div")
    container.classList.add("location-filter-grabber")
    for (let i = 0; i < 9; i++) {
        const inner = document.createElement("div")
        container.appendChild(inner)
    }
    return container
}

const createCornerElement = (): HTMLElement => {
    const container = document.createElement("div")
    container.classList.add("location-filter-corner")
    return container
}

const getMaskData = ([minLon, minLat, maxLon, maxLat]: Bounds): GeoJSON => {
    // Normalize bounds
    if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon]
    if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat]
    if (minLon < -180 || minLon > 180) minLon = mod(minLon + 180, 360) - 180
    if (maxLon < -180 || maxLon > 180) maxLon = mod(maxLon + 180, 360) - 180

    const crossesAntimeridian = minLon > maxLon
    if (!crossesAntimeridian) {
        // Simple case: single polygon with a hole
        return {
            type: "Feature",
            properties: {},
            geometry: {
                type: "Polygon",
                coordinates: [
                    [
                        [-180, -85],
                        [-180, 85],
                        [180, 85],
                        [180, -85],
                        [-180, -85],
                    ],
                    [
                        [minLon, minLat],
                        [maxLon, minLat],
                        [maxLon, maxLat],
                        [minLon, maxLat],
                        [minLon, minLat],
                    ],
                ],
            },
        }
    }

    // Split into two holes
    return {
        type: "Feature",
        properties: {},
        geometry: {
            type: "Polygon",
            coordinates: [
                [
                    [-180, -85], // Outer ring
                    [-180, 85],
                    [180, 85],
                    [180, -85],
                    [-180, -85],
                ],
                [
                    [minLon, minLat], // Eastern hole
                    [180, minLat],
                    [180, maxLat],
                    [minLon, maxLat],
                    [minLon, minLat],
                ],
                [
                    [-180, minLat], // Western hole
                    [maxLon, minLat],
                    [maxLon, maxLat],
                    [-180, maxLat],
                    [-180, minLat],
                ],
            ],
        },
    }
}
