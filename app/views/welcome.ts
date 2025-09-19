import { encodeMapState, type MapState } from "./lib/map/map-utils"
import { mount } from "./lib/mount"
import { qsEncode, qsParse } from "./lib/qs"
import { isLatitude, isLongitude, isZoom } from "./lib/utils"

mount("welcome-body", (body) => {
    const noteLink = body.querySelector("a.note-link")
    const startButton = body.querySelector("a.start-btn")

    // Support default location setting via URL parameters
    let providedState: MapState | null = null
    const params = qsParse(window.location.search)
    if (params.lon && params.lat) {
        const lon = Number.parseFloat(params.lon)
        const lat = Number.parseFloat(params.lat)
        const zoom = params.zoom ? Number.parseFloat(params.zoom) : 17
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            providedState = { lon, lat, zoom, layersCode: params.layers }
        }
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (providedState) noteHref += encodeMapState(providedState)
    noteLink.href = noteHref

    // Passthrough supported parameters
    const startParams: { [key: string]: string } = {}
    if (params.editor) startParams.editor = params.editor

    if (providedState) {
        // If location was provided, redirect to /edit with the provided coordinates
        let startHref = "/edit"
        if (Object.keys(startParams).length) startHref += `?${qsEncode(startParams)}`
        startHref += encodeMapState(providedState)
        startButton.href = startHref
    } else {
        // If location was not provided, request navigator.geolocation
        /** On geolocation success, redirect to /edit with the returned coordinates */
        const onGeolocationSuccess = (position: GeolocationPosition) => {
            console.debug("onGeolocationSuccess", position)
            const lon = position.coords.longitude
            const lat = position.coords.latitude
            const zoom = 17
            const geolocationState: MapState = {
                lon,
                lat,
                zoom,
                layersCode: params.layers,
            }

            let startHref = "/edit"
            if (Object.keys(startParams).length)
                startHref += `?${qsEncode(startParams)}`
            startHref += encodeMapState(geolocationState)
            startButton.href = startHref
            startButton.removeEventListener("click", onStartButtonClick)
        }

        /** On geolocation failure, remove event listener */
        const onGeolocationFailure = () => {
            console.debug("onGeolocationFailure")
            startButton.removeEventListener("click", onStartButtonClick)
        }

        const onStartButtonClick = (e: Event) => {
            e.preventDefault()
            navigator.geolocation.getCurrentPosition(
                (position: GeolocationPosition) => {
                    onGeolocationSuccess(position)
                    window.location.href = startButton.href
                },
                () => {
                    onGeolocationFailure()
                    window.location.href = startButton.href
                },
                {
                    maximumAge: 28800_000, // 8 hours
                    timeout: 10_000, // 10 seconds
                },
            )
        }

        // If permission was granted, start geolocation early
        navigator.permissions?.query({ name: "geolocation" }).then((result) => {
            console.debug("permissions.geolocation", result.state)
            if (result.state === "granted") {
                navigator.geolocation.getCurrentPosition(
                    onGeolocationSuccess,
                    onGeolocationFailure,
                    {
                        maximumAge: 28800_000, // 8 hours
                        timeout: 60_000, // 60 seconds
                    },
                )
            }
        })

        startButton.addEventListener("click", onStartButtonClick, { once: true })
    }
})
