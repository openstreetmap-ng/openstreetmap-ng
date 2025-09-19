import { config } from "./config"
import { getTimezoneName } from "./format"
import { timezoneUpdateTimeStorage } from "./local-storage"
import { getUnixTimestamp, requestIdleCallbackPolyfill } from "./utils"

const updateDelay = 24 * 3600 // 1 day

const timezoneUpdate = (): void => {
    const last = timezoneUpdateTimeStorage.get()
    const now = getUnixTimestamp()
    if (last && last + updateDelay > now) return

    timezoneUpdateTimeStorage.set(now)
    const timezone = getTimezoneName()
    console.debug("Updating user timezone", timezone)

    const formData = new FormData()
    formData.append("timezone", timezone)

    fetch("/api/web/user/timezone", {
        method: "POST",
        body: formData,
        mode: "same-origin",
        cache: "no-store",
        priority: "low",
    })
        .then((resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
            console.debug("Successfully updated user timezone")
        })
        .catch((error) => {
            console.warn("Failed to update user timezone", error)
        })
}

if (config.userConfig)
    setTimeout(() => {
        requestIdleCallbackPolyfill(timezoneUpdate, { timeout: 10_000 })
    }, 10_000)
