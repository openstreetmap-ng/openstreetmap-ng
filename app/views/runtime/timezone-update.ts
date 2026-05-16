import { Service } from "@proto/settings_pb"
import { DAY, SECOND } from "@std/datetime/constants"
import { isLoggedIn } from "@utils/config"
import { getTimezoneName } from "@utils/format"
import { timezoneUpdateTimeStorage } from "@utils/local-storage"
import { rpcUnary } from "@utils/rpc"

const UPDATE_DELAY = DAY

const timezoneUpdate = async () => {
  const last = timezoneUpdateTimeStorage.get()
  const now = Date.now()
  if (last && last + UPDATE_DELAY > now) return

  timezoneUpdateTimeStorage.set(now)
  const timezone = getTimezoneName()
  console.debug("TimezoneUpdate: Updating to", timezone)

  try {
    await rpcUnary(Service.method.updateTimezone)({ timezone })
    console.debug("TimezoneUpdate: Success")
  } catch (error) {
    console.warn("TimezoneUpdate: Failed", error)
  }
}

if (isLoggedIn)
  setTimeout(() => {
    requestIdleCallback(timezoneUpdate, { timeout: 10 * SECOND })
  }, 10 * SECOND)
