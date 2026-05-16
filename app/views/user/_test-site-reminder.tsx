import { BPopover } from "@components/bootstrap"
import { ENV } from "@utils/config"
import type { VNode } from "preact"

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
