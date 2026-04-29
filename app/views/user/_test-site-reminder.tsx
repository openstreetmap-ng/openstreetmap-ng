import { ENV } from "@lib/config"
import type { VNode } from "preact"
import { BPopover } from "../lib/bootstrap"

export const TestSiteReminder = ({ children }: { children: VNode }) => (
  <BPopover
    trigger="focus"
    disabled={ENV === "prod"}
    content={() => (
      <>
        <strong>Test Site Reminder</strong>
        <p class="mb-0 small">
          Use fake data only. Do not provide real email addresses. All emails go to
          mail.openstreetmap.ng
        </p>
      </>
    )}
  >
    {children}
  </BPopover>
)
