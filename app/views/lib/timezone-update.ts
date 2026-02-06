import { isLoggedIn } from "@lib/config"
import { getTimezoneName } from "@lib/format"
import { timezoneUpdateTimeStorage } from "@lib/local-storage"
import { SettingsService } from "@lib/proto/settings_pb"
import { rpcUnary } from "@lib/rpc"
import { DAY, SECOND } from "@std/datetime/constants"

const UPDATE_DELAY = DAY

const timezoneUpdate = async () => {
  const last = timezoneUpdateTimeStorage.get()
  const now = Date.now()
  if (last && last + UPDATE_DELAY > now) return

  timezoneUpdateTimeStorage.set(now)
  const timezone = getTimezoneName()
  console.debug("TimezoneUpdate: Updating to", timezone)

  try {
    await rpcUnary(SettingsService.method.updateTimezone)({ timezone })
    console.debug("TimezoneUpdate: Success")
  } catch (error) {
    console.warn("TimezoneUpdate: Failed", error)
  }
}

if (isLoggedIn)
  setTimeout(() => {
    requestIdleCallback(timezoneUpdate, { timeout: 10 * SECOND })
  }, 10 * SECOND)
