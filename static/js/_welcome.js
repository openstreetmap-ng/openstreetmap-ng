import { qsParse, qsStringify } from "./_qs.js"
import { formatHash, isLatitude, isLongitude, isZoom } from "./_utils.js"

const noteIcon = document.querySelector(".welcome-note-link")
if (noteIcon) {
    const startButton = document.querySelector(".welcome-start-btn")

    // Support default location setting via URL parameters
    let locationProvided = false
    const params = qsParse(window.location.search.substring(1))
    if (params.lat && params.lon) {
        // Zoom is optional, default to 17
        params.zoom = parseInt(params.zoom || 17, 10)
        params.lat = parseFloat(params.lat)
        params.lon = parseFloat(params.lon)

        if (isZoom(params.zoom) && isLatitude(params.lat) && isLongitude(params.lon)) locationProvided = true
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (locationProvided) noteHref += formatHash(params)
    noteIcon.setAttribute("href", noteHref)

    let startHref = "/edit"

    // Passthrough supported parameters
    const startParams = {}
    if (params.editor) startParams.editor = params.editor

    if (!locationProvided) {
        // If location was not provided, request navigator.geolocation
        // On geolocation success, redirect to /edit with the returned coordinates
        const onGeolocationSuccess = (position) => {
            params.zoom = 17
            params.lat = position.coords.latitude
            params.lon = position.coords.longitude

            if (Object.keys(startParams).length > 0) startHref += `?${qsStringify(startParams)}`
            startHref += formatHash(params)
            window.location = startHref
        }

        // On geolocation failure, redirect to /?edit_help=1
        const onGeolocationFailure = () => {
            window.location = "/?edit_help=1"
        }

        if (navigator.geolocation) {
            startButton.on("click", (e) => {
                e.preventDefault()
                startButton.disabled = true
                startButton.addClass("loading")
                navigator.geolocation.getCurrentPosition(onGeolocationSuccess, onGeolocationFailure, {
                    maximumAge: 28800_000, // 8 hours
                    timeout: 10_000, // 10 seconds
                })
            })
        } else {
            // If navigator.geolocation is not supported, redirect to /?edit_help=1
            startButton.setAttribute("href", "/?edit_help=1")
        }
    } else {
        // If location was provided, redirect to /edit with the provided coordinates
        if (Object.keys(startParams).length > 0) startHref += `?${qsStringify(startParams)}`
        startHref += formatHash(params)
        startButton.setAttribute("href", startHref)
    }
}
