import { isLoggedIn } from "@lib/config"
import { getTimezoneName } from "@lib/format"
import { timezoneUpdateTimeStorage } from "@lib/local-storage"
import { requestIdleCallbackPolyfill } from "@lib/polyfills"
import { assert } from "@std/assert"
import { DAY, SECOND } from "@std/datetime/constants"

const UPDATE_DELAY = 1 * DAY

const timezoneUpdate = async () => {
    const last = timezoneUpdateTimeStorage.get()
    const now = Date.now()
    if (last && last + UPDATE_DELAY > now) return

    timezoneUpdateTimeStorage.set(now)
    const timezone = getTimezoneName()
    console.debug("TimezoneUpdate: Updating to", timezone)

    const formData = new FormData()
    formData.append("timezone", timezone)

    try {
        const resp = await fetch("/api/web/user/timezone", {
            method: "POST",
            body: formData,
            priority: "low",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)
        console.debug("TimezoneUpdate: Success")
    } catch (error) {
        console.warn("TimezoneUpdate: Failed", error)
    }
}

if (isLoggedIn)
    setTimeout(() => {
        requestIdleCallbackPolyfill(timezoneUpdate, { timeout: 10 * SECOND })
    }, 10 * SECOND)
