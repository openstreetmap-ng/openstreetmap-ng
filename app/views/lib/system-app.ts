import { API_URL } from "@lib/config"
import { systemAppAccessTokenStorage } from "@lib/local-storage"
import { wrapMessageEventValidator } from "@lib/utils"
import { assert } from "@std/assert"

/** Load system app access token and call successCallback with it */
const loadSystemApp = async (
    clientId: string,
    successCallback: (token: string) => void,
) => {
    console.debug("SystemApp: Loading", clientId)

    const accessToken = systemAppAccessTokenStorage(clientId).get()
    if (!accessToken) {
        createAccessToken(clientId, successCallback)
        return
    }

    try {
        const resp = await fetch(`${API_URL}/api/0.6/user/details`, {
            credentials: "omit",
            headers: { authorization: `Bearer ${accessToken}` },
            priority: "high",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)
        console.debug("SystemApp: Using cached token")
        successCallback(accessToken)
    } catch {
        console.debug("SystemApp: Cached token invalid")
        createAccessToken(clientId, successCallback)
    }
}

const createAccessToken = async (
    clientId: string,
    successCallback: (token: string) => void,
) => {
    console.debug("SystemApp: Creating token")

    const formData = new FormData()
    formData.append("client_id", clientId)

    try {
        const resp = await fetch("/api/web/system-app/create-access-token", {
            method: "POST",
            body: formData,
            priority: "high",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const data = await resp.json()
        const accessToken = data.access_token
        systemAppAccessTokenStorage(clientId).set(accessToken)
        successCallback(accessToken)
    } catch (error) {
        console.error("SystemApp: Failed to create token", error)
        alert(error.message)
    }
}

/** Configure iframe to load system app */
export const configureIFrameSystemApp = (
    clientId: string,
    iframe: HTMLIFrameElement,
    iframeOrigin: string,
) => {
    console.debug("SystemApp: Configuring iframe", { clientId, iframeOrigin })

    /** Handle load system app requests, obtain token and respond back */
    const onWindowMessage = wrapMessageEventValidator(
        ({ data, origin }: MessageEvent) => {
            if (data.type !== "loadSystemApp") return
            // Respond only once
            window.removeEventListener("message", onWindowMessage)
            console.debug("SystemApp: Request received from", origin)
            loadSystemApp(clientId, (accessToken) => {
                console.debug("SystemApp: Responding to", iframeOrigin)
                iframe.contentWindow!.postMessage(
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
) => {
    console.debug("SystemApp: Parent load request")

    /** Handle load system app response, call successCallback with access token */
    const onWindowMessage = wrapMessageEventValidator(
        ({ data, origin }: MessageEvent) => {
            if (data.type !== "loadedSystemApp") return
            // Respond only once
            window.removeEventListener("message", onWindowMessage)
            console.debug("SystemApp: Response received from", origin)
            successCallback(data.accessToken, origin)
        },
        false,
    )
    window.addEventListener("message", onWindowMessage)

    // Request system app load
    window.parent.postMessage({ type: "loadSystemApp" }, "*") // wildcard publish: nothing sensitive
}
