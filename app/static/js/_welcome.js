import { qsEncode, qsParse } from "./_qs.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const welcomeBody = document.querySelector("body.welcome-body")
if (welcomeBody) {
    const noteLink = welcomeBody.querySelector(".note-link")
    const startButton = welcomeBody.querySelector(".start-btn")

    // Support default location setting via URL parameters
    let locationProvided = false
    const params = qsParse(location.search.substring(1))
    if (params.lon && params.lat) {
        params.lon = parseFloat(params.lon)
        params.lat = parseFloat(params.lat)
        // Zoom is optional, defaults to 17
        params.zoom = parseInt(params.zoom ?? 17, 10)

        if (isLongitude(params.lon) && isLatitude(params.lat) && isZoom(params.zoom)) {
            locationProvided = true
        }
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (locationProvided) noteHref += encodeMapState(params)
    noteLink.href = noteHref

    // Passthrough supported parameters
    const startParams = {}
    if (params.editor) startParams.editor = params.editor

    if (locationProvided) {
        // If location was provided, redirect to /edit with the provided coordinates
        let startHref = "/edit"
        if (Object.keys(startParams).length) startHref += `?${qsEncode(startParams)}`
        startHref += encodeMapState(params)
        startButton.href = startHref
    } else {
        // If location was not provided, request navigator.geolocation
        // On geolocation success, redirect to /edit with the returned coordinates
        const onGeolocationSuccess = (position) => {
            console.debug("onGeolocationSuccess", position)
            params.lon = position.coords.longitude
            params.lat = position.coords.latitude
            params.zoom = 17

            let startHref = "/edit"
            if (Object.keys(startParams).length) startHref += `?${qsEncode(startParams)}`
            startHref += encodeMapState(params)
            startButton.href = startHref
            startButton.removeEventListener("click", onStartButtonClick)
        }

        const onGeolocationFailure = () => {
            console.debug("onGeolocationFailure")
            startButton.removeEventListener("click", onStartButtonClick)
        }

        const onStartButtonClick = (e) => {
            e.preventDefault()

            const onGeolocationSuccessWrapped = (position) => {
                onGeolocationSuccess(position)
                location = startButton.getAttribute("href")
            }

            const onGeolocationFailureWrapped = () => {
                onGeolocationFailure()
                location = startButton.getAttribute("href")
            }

            navigator.geolocation.getCurrentPosition(onGeolocationSuccessWrapped, onGeolocationFailureWrapped, {
                maximumAge: 28800_000, // 8 hours
                timeout: 10_000, // 10 seconds
            })
        }

        // If permission was granted, start geolocation early
        navigator.permissions?.query({ name: "geolocation" }).then((result) => {
            console.debug("permissions.geolocation", result.state)
            if (result.state === "granted") {
                navigator.geolocation.getCurrentPosition(onGeolocationSuccess, onGeolocationFailure, {
                    maximumAge: 28800_000, // 8 hours
                    timeout: 60_000, // 60 seconds
                })
            }
        })

        startButton.addEventListener("click", onStartButtonClick, { once: true })
    }
}
