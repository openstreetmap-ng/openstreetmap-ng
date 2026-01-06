import type { ComponentChild } from "preact"
import { render } from "preact"

export const mountMapAlert = (node: ComponentChild) => {
  const container = document.getElementById("MapAlerts")!
  const mountPoint = document.createElement("div")
  render(node, mountPoint)
  container.append(mountPoint)
}

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
