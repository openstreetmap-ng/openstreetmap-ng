import type { GeoJSON } from "geojson"
import { type GeoJSONSource, type IControl, LngLatBounds, type Map as MaplibreMap, Marker } from "maplibre-gl"
import type { Bounds } from "../_types"
import { throttle } from "../_utils.ts"
import { type LayerId, addMapLayer, emptyFeatureCollection, layersConfig, removeMapLayer } from "./_layers"

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
        },
    },
})

const dragThrottleDelay = 16 // 60 FPS

export class LocationFilterControl implements IControl {
    private _map: MaplibreMap
    private _bounds: Bounds
    private _grabber: Marker
    private _corners: Marker[]
    private _onRenderHandlers: (() => void)[] = []

    public addTo(map: MaplibreMap, bounds: LngLatBounds): this {
        this._map = map
        addMapLayer(map, layerId)

        const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
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
            throttle(() => this._processMarkerUpdate(-1), dragThrottleDelay),
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
                throttle(() => this._processMarkerUpdate(i), dragThrottleDelay),
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

    // public setBounds(bounds: LngLatBounds): void {
    //     const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
    //     this._bounds = [minLon, minLat, maxLon, maxLat]
    //     this._render()
    // }

    public getBounds(): LngLatBounds {
        let [minLon, minLat, maxLon, maxLat] = this._bounds
        if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon]
        if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat]
        return new LngLatBounds([minLon, minLat, maxLon, maxLat])
    }

    private _processMarkerUpdate(i: number) {
        const [minLon, minLat, maxLon, maxLat] = this._bounds
        if (i === -1) {
            const lngLat = this._grabber.getLngLat()
            const [minLon, minLat, maxLon, maxLat] = this._bounds
            const deltaX = lngLat.lng - minLon
            const deltaY = lngLat.lat - maxLat
            this._bounds = [minLon + deltaX, minLat + deltaY, maxLon + deltaX, maxLat + deltaY]
        } else if (i === 0) {
            const lngLat = this._corners[0].getLngLat()
            this._bounds = [lngLat.lng, lngLat.lat, maxLon, maxLat]
        } else if (i === 1) {
            const lngLat = this._corners[1].getLngLat()
            this._bounds = [lngLat.lng, minLat, maxLon, lngLat.lat]
        } else if (i === 2) {
            const lngLat = this._corners[2].getLngLat()
            this._bounds = [minLon, minLat, lngLat.lng, lngLat.lat]
        } else if (i === 3) {
            const lngLat = this._corners[3].getLngLat()
            this._bounds = [minLon, lngLat.lat, lngLat.lng, maxLat]
        } else {
            console.warn("Invalid marker index", i)
            return
        }
        this._render(i)
    }

    private _render(i?: number): void {
        const [minLon, minLat, maxLon, maxLat] = this._bounds
        if (i !== -1) this._grabber.setLngLat([Math.min(minLon, maxLon), Math.max(minLat, maxLat)])
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
        return undefined
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

const getMaskData = (bounds: Bounds, maxBounds?: LngLatBounds): GeoJSON => {
    maxBounds ??= new LngLatBounds([-180, -85, 180, 85])
    const [[mapMinLon, mapMinLat], [mapMaxLon, mapMaxLat]] = maxBounds.toArray()
    const [minLon, minLat, maxLon, maxLat] = bounds
    return {
        type: "Feature",
        properties: {},
        geometry: {
            type: "Polygon",
            coordinates: [
                [
                    [mapMinLon, mapMinLat],
                    [mapMinLon, mapMaxLat],
                    [mapMaxLon, mapMaxLat],
                    [mapMaxLon, mapMinLat],
                    [mapMinLon, mapMinLat],
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
