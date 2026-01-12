import { Alert, Popover, Tooltip } from "bootstrap"
import type { ComponentChild } from "preact"
import { useEffect, useRef } from "preact/hooks"

export const BTooltip = ({
  title,
  placement,
  children,
}: {
  title: string | undefined
  placement?: Tooltip.Options["placement"] | undefined
  children: ComponentChild
}) => {
  const wrapperRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (title === undefined) return

    const options: Partial<Tooltip.Options> = { title }
    if (placement !== undefined) options.placement = placement

    const tooltip = new Tooltip(wrapperRef.current!, options)
    return () => tooltip.dispose()
  }, [title, placement])

  return <span ref={wrapperRef}>{children}</span>
}

export const configureBootstrapTooltips = (root: ParentNode) => {
  for (const element of root.querySelectorAll("[data-bs-toggle=tooltip]")) {
    Tooltip.getOrCreateInstance(element)
  }
}

export const configureBootstrapAlerts = (root: ParentNode) => {
  for (const element of root.querySelectorAll(".alert")) {
    Alert.getOrCreateInstance(element)
  }
}

export const configureBootstrapPopovers = (root: ParentNode) => {
  for (const element of root.querySelectorAll("[data-bs-toggle=popover]")) {
    Popover.getOrCreateInstance(element)
  }
}

configureBootstrapTooltips(document)
configureBootstrapAlerts(document)
configureBootstrapPopovers(document)
