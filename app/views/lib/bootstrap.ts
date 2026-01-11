import { type ReadonlySignal, useSignal, useSignalEffect } from "@preact/signals"
import { Alert, Popover, Tooltip } from "bootstrap"
import type { RefCallback } from "preact"

export const useTooltip = (
  getOptions: () => Partial<Tooltip.Options>,
  enabled?: ReadonlySignal<boolean>,
) => {
  const target = useSignal<HTMLElement | null>(null)
  const instance = useSignal<Tooltip | null>(null)

  useSignalEffect(() => {
    const node = target.value
    if (!node) return

    const tooltip = new Tooltip(node, getOptions())
    instance.value = tooltip
    return () => {
      tooltip.dispose()
      instance.value = null
    }
  })

  useSignalEffect(() => {
    const tooltip = instance.value
    if (!tooltip) return

    if (enabled && !enabled.value) {
      tooltip.disable()
      tooltip.hide()
    } else {
      tooltip.enable()
    }
  })

  return ((node: HTMLElement | null) => {
    target.value = node
  }) satisfies RefCallback<HTMLElement>
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
