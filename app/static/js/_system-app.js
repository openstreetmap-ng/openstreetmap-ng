import { getSystemAppAccessToken, setSystemAppAccessToken } from "./_local-storage.js"

/**
 * Load system app access token and call successCallback with it
 * @param {string} clientId System app client ID
 * @param {function} successCallback Callback to call with access token
 * @returns {void}
 */
const loadSystemApp = (clientId, successCallback) => {
    console.debug("loadSystemApp", clientId)

    const accessToken = getSystemAppAccessToken(clientId)
    if (!accessToken) {
        createAccessToken(clientId, successCallback)
        return
    }

    return fetch("/api/0.6/user/details", {
        method: "GET",
        credentials: "omit",
        headers: { authorization: `Bearer ${accessToken}` },
        mode: "same-origin",
        cache: "no-store",
        priority: "high",
    })
        .then((resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
            console.debug("Using cached system app access token")
            successCallback(accessToken)
        })
        .catch((error) => {
            console.debug("Cached system app access token is invalid")
            createAccessToken(clientId, successCallback)
        })
}

const createAccessToken = (clientId, successCallback) => {
    console.debug("Creating system app access token")

    const formData = new FormData()
    formData.append("client_id", clientId)

    fetch("/api/web/system-app/create-access-token", {
        method: "POST",
        body: formData,
        mode: "same-origin",
        cache: "no-store",
        priority: "high",
    })
        .then(async (resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

            const data = await resp.json()
            const accessToken = data.access_token
            setSystemAppAccessToken(clientId, accessToken)
            successCallback(accessToken)
        })
        .catch((error) => {
            console.error("Failed to create system app access token", error)
            alert(error.message)
        })
}

/**
 * Configure iframe to load system app
 * @param {string} clientId System app client ID
 * @param {HTMLIFrameElement} iframe IFrame element
 * @param {string} iframeOrigin IFrame origin
 * @returns {void}
 */
export const configureIFrameSystemApp = (clientId, iframe, iframeOrigin) => {
    console.debug("configureIFrameSystemApp", clientId, iframeOrigin)

    /**
     * Handle load system app requests, obtain token and respond back
     * @param {MessageEvent} event
     */
    const onWindowMessage = (event) => {
        const data = event.data
        if (data.type === "loadSystemApp") {
            // Respond only once
            removeEventListener("message", onWindowMessage)

            console.debug("Received loadSystemApp request")
            loadSystemApp(clientId, (accessToken) => {
                console.debug("Responding to loadSystemApp request")
                iframe.contentWindow.postMessage({ type: "loadedSystemApp", accessToken }, iframeOrigin)
            })
        }
    }

    // Listen for events
    addEventListener("message", onWindowMessage)
}

/**
 * Communicate with parent window to load system app
 * @param {function} successCallback Callback to call with access token
 * @returns {void}
 */
export const parentLoadSystemApp = (successCallback) => {
    console.debug("parentLoadSystemApp")

    /**
     * Handle load system app response, call successCallback with access token
     * @param {MessageEvent} event
     */
    const onWindowMessage = (event) => {
        const data = event.data
        if (data.type === "loadedSystemApp") {
            // Respond only once
            removeEventListener("message", onWindowMessage)

            console.debug("Received loadSystemApp response")
            successCallback(data.accessToken)
        }
    }

    // Listen for events
    addEventListener("message", onWindowMessage)

    // Request system app load
    parent.postMessage({ type: "loadSystemApp" }, "*")
}
