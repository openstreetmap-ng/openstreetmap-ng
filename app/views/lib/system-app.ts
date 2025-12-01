import { config } from "./config"
import { systemAppAccessTokenStorage } from "./local-storage"
import { wrapMessageEventValidator } from "./utils"

/** Load system app access token and call successCallback with it */
const loadSystemApp = (
    clientId: string,
    successCallback: (token: string) => void,
): void => {
    console.debug("loadSystemApp", clientId)

    const accessToken = systemAppAccessTokenStorage(clientId).get()
    if (!accessToken) {
        createAccessToken(clientId, successCallback)
        return
    }

    fetch(`${config.apiUrl}/api/0.6/user/details`, {
        credentials: "omit",
        headers: { authorization: `Bearer ${accessToken}` },
        priority: "high",
    })
        .then((resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
            console.debug("Using cached system app access token")
            successCallback(accessToken)
        })
        .catch(() => {
            console.debug("Cached system app access token is invalid")
            createAccessToken(clientId, successCallback)
        })
}

const createAccessToken = (
    clientId: string,
    successCallback: (token: string) => void,
): void => {
    console.debug("Creating system app access token")

    const formData = new FormData()
    formData.append("client_id", clientId)

    fetch("/api/web/system-app/create-access-token", {
        method: "POST",
        body: formData,
        priority: "high",
    })
        .then(async (resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

            const data = await resp.json()
            const accessToken = data.access_token
            systemAppAccessTokenStorage(clientId).set(accessToken)
            successCallback(accessToken)
        })
        .catch((error) => {
            console.error("Failed to create system app access token", error)
            alert(error.message)
        })
}

/** Configure iframe to load system app */
export const configureIFrameSystemApp = (
    clientId: string,
    iframe: HTMLIFrameElement,
    iframeOrigin: string,
): void => {
    console.debug("configureIFrameSystemApp", clientId, iframeOrigin)

    /** Handle load system app requests, obtain token and respond back */
    const onWindowMessage = wrapMessageEventValidator(
        ({ data, origin }: MessageEvent): void => {
            if (data.type !== "loadSystemApp") return
            // Respond only once
            window.removeEventListener("message", onWindowMessage)
            console.debug("Received loadSystemApp request from", origin)
            loadSystemApp(clientId, (accessToken) => {
                console.debug("Responding to loadSystemApp request to", iframeOrigin)
                iframe.contentWindow.postMessage(
                    { type: "loadedSystemApp", accessToken },
                    iframeOrigin,
                )
            })
        },
    )
    window.addEventListener("message", onWindowMessage)
}

/** Communicate with parent window to load system app */
export const parentLoadSystemApp = (
    successCallback: (token: string, parentOrigin: string) => void,
): void => {
    console.debug("parentLoadSystemApp")

    /** Handle load system app response, call successCallback with access token */
    const onWindowMessage = wrapMessageEventValidator(
        ({ data, origin }: MessageEvent): void => {
            if (data.type !== "loadedSystemApp") return
            // Respond only once
            window.removeEventListener("message", onWindowMessage)
            console.debug("Received loadSystemApp response from", origin)
            successCallback(data.accessToken, origin)
        },
        false,
    )
    window.addEventListener("message", onWindowMessage)

    // Request system app load
    window.parent.postMessage({ type: "loadSystemApp" }, "*") // wildcard publish: nothing sensitive
}
