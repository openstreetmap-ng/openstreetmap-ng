import { signal } from "@preact/signals"
import type { ComponentChild } from "preact"

const alerts = signal<
  readonly Readonly<{
    id: symbol
    node: ComponentChild
  }>[]
>([])

export const pushMapAlert = (node: ComponentChild) => {
  const id = Symbol("map-alert")
  alerts.value = [...alerts.peek(), { id, node }]
  return () => {
    alerts.value = alerts.peek().filter((a) => a.id !== id)
  }
}

export const MapAlerts = () => (
  <div class="map-alerts">
    {alerts.value.map((a) => (
      <div key={a.id}>{a.node}</div>
    ))}
  </div>
)

export const MapAlertPanel = ({
  variant,
  children,
}: {
  variant: "warning" | "danger" | "info" | "success"
  children: ComponentChild
}) => (
  <div
    class={`alert alert-${variant} map-alert`}
    role="alert"
  >
    {children}
  </div>
)
