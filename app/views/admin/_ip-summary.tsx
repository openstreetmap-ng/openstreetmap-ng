import { BPopover } from "@lib/bootstrap"
import type { IpCountValid } from "@lib/proto/shared_pb"
import { formatPackedIp } from "@lib/utils"

export const IpSummary = ({ ipCounts }: { ipCounts: readonly IpCountValid[] }) => {
  const mainIp = ipCounts[0]
  if (!mainIp) return <span class="text-body-secondary">&mdash;</span>
  const mainIpText = formatPackedIp(mainIp.ip)

  return (
    <>
      <a
        href={`/audit?ip=${encodeURIComponent(mainIpText)}`}
        class={mainIp.count >= 2 ? "text-bg-warning rounded" : "text-body-secondary"}
      >
        {mainIpText}
      </a>
      {mainIp.count > 1 && <small class="text-muted ms-1">&times;{mainIp.count}</small>}
      {ipCounts.length > 1 && (
        <BPopover
          trigger="hover focus"
          content={() => (
            <>
              {ipCounts.map((item, index) => {
                if (index === 0) return null
                const ip = formatPackedIp(item.ip)
                return (
                  <div key={ip}>
                    <a href={`/audit?ip=${encodeURIComponent(ip)}`}>{ip}</a>{" "}
                    <small>&times;{item.count}</small>
                  </div>
                )
              })}
            </>
          )}
        >
          <span class="text-primary ms-1">+{ipCounts.length - 1} more</span>
        </BPopover>
      )}
    </>
  )
}
