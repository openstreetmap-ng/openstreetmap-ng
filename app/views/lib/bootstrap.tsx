import { useDisposeEffect } from "@lib/dispose-scope"
import { Alert, Collapse, Popover, Tooltip } from "bootstrap"
import {
  type ComponentChild,
  type ComponentChildren,
  render,
  type TargetedMouseEvent,
} from "preact"
import { useEffect, useId, useRef, useState } from "preact/hooks"

export const BAccordion = ({
  header,
  children,
  class: className = "",
  defaultOpen = false,
  open,
  onOpenChange,
}: {
  header: ComponentChildren
  children: ComponentChildren
  class?: string
  defaultOpen?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) => {
  const isControlled = open !== undefined
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen)
  const isOpen = isControlled ? open : uncontrolledOpen

  const collapseId = useId()
  const collapseRef = useRef<HTMLDivElement>(null)
  const collapseInstanceRef = useRef<Collapse>()

  useEffect(() => {
    const element = collapseRef.current!
    const collapse = new Collapse(element, { toggle: false })
    collapseInstanceRef.current = collapse
    return () => {
      collapse.dispose()
    }
  }, [])

  useDisposeEffect(
    (scope) => {
      const element = collapseRef.current!
      scope.dom(element, "shown.bs.collapse", () => {
        if (!isControlled) setUncontrolledOpen(true)
        onOpenChange?.(true)
      })
      scope.dom(element, "hidden.bs.collapse", () => {
        if (!isControlled) setUncontrolledOpen(false)
        onOpenChange?.(false)
      })
    },
    [isControlled, onOpenChange],
  )

  useEffect(() => {
    if (!isControlled || !collapseInstanceRef.current) return
    if (open) {
      collapseInstanceRef.current.show()
    } else {
      collapseInstanceRef.current.hide()
    }
  }, [isControlled, open])

  const onToggleClick = (event: TargetedMouseEvent<HTMLButtonElement>) => {
    const target = event.target as Element
    const interactiveTarget = target.closest("a,button,input,select,textarea,label")
    if (interactiveTarget && interactiveTarget !== event.currentTarget) return
    collapseInstanceRef.current?.toggle()
  }

  return (
    <div class={`accordion ${className}`}>
      <div class="accordion-header">
        <button
          class={isOpen ? "accordion-button" : "accordion-button collapsed"}
          type="button"
          aria-expanded={isOpen}
          aria-controls={collapseId}
          onClick={onToggleClick}
        >
          {header}
        </button>
      </div>
      <div
        id={collapseId}
        class={`accordion-collapse collapse ${isOpen ? "show" : ""}`}
        ref={collapseRef}
      >
        <div class="accordion-body">{children}</div>
      </div>
    </div>
  )
}

export const BPopover = ({
  content,
  trigger,
  children,
}: {
  content: () => ComponentChild
  trigger?: Popover.Options["trigger"] | undefined
  children: ComponentChild
}) => {
  const wrapperRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const contentNode = document.createElement("div")
    render(content(), contentNode)

    const options: Partial<Popover.Options> = {
      html: true,
      container: "body",
      content: () => contentNode,
    }
    if (trigger !== undefined) options.trigger = trigger

    const popover = new Popover(wrapperRef.current!, options)

    return () => {
      popover.dispose()
      render(null, contentNode)
    }
  }, [content, trigger])

  return <span ref={wrapperRef}>{children}</span>
}

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
