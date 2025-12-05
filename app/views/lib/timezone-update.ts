import { config } from "@lib/config"
import { getTimezoneName } from "@lib/format"
import { timezoneUpdateTimeStorage } from "@lib/local-storage"
import { requestIdleCallbackPolyfill } from "@lib/polyfills"
import { getUnixTimestamp } from "@lib/utils"

const UPDATE_DELAY = 24 * 3600 // 1 day

const timezoneUpdate = async () => {
    const last = timezoneUpdateTimeStorage.get()
    const now = getUnixTimestamp()
    if (last && last + UPDATE_DELAY > now) return

    timezoneUpdateTimeStorage.set(now)
    const timezone = getTimezoneName()
    console.debug("Updating user timezone", timezone)

    const formData = new FormData()
    formData.append("timezone", timezone)

    try {
        const resp = await fetch("/api/web/user/timezone", {
            method: "POST",
            body: formData,
            priority: "low",
        })
        if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
        console.debug("Successfully updated user timezone")
    } catch (error) {
        console.warn("Failed to update user timezone", error)
    }
}

if (config.userConfig)
    setTimeout(() => {
        requestIdleCallbackPolyfill(timezoneUpdate, { timeout: 10_000 })
    }, 10_000)
