import { useDisposeEffect } from "@lib/dispose-scope"
import { Alert, Collapse, Popover, Tooltip } from "bootstrap"
import {
  cloneElement,
  type ComponentChild,
  type ComponentChildren,
  type Ref,
  render,
  type TargetedMouseEvent,
  type VNode,
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
  disabled = false,
  children,
}: {
  content: () => ComponentChild
  trigger?: Popover.Options["trigger"] | undefined
  disabled?: boolean
  children: VNode
}) => {
  const targetRef = useRef<Element>(null)
  const childRef = children.ref as Ref<Element> | undefined

  const setTargetRef = (element: Element | null) => {
    targetRef.current = element
    if (typeof childRef === "function") {
      childRef(element)
    } else if (childRef) {
      childRef.current = element
    }
  }

  useEffect(() => {
    if (disabled) return

    let contentNode: HTMLDivElement | undefined

    const options: Partial<Popover.Options> = {
      html: true,
      container: "body",
      content: () => {
        if (!contentNode) {
          contentNode = document.createElement("div")
          render(content(), contentNode)
        }
        return contentNode
      },
    }
    if (trigger) options.trigger = trigger

    const popover = new Popover(targetRef.current!, options)

    return () => {
      popover.dispose()
      if (contentNode) render(null, contentNode)
    }
  }, [content, disabled, trigger])

  return disabled ? children : cloneElement(children, { ref: setTargetRef })
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
    if (!title) return

    const options: Partial<Tooltip.Options> = { title }
    if (placement) options.placement = placement

    const tooltip = new Tooltip(wrapperRef.current!, options)
    return () => tooltip.dispose()
  }, [title, placement])

  return <span ref={wrapperRef}>{children}</span>
}

for (const element of document.querySelectorAll("[data-bs-toggle=tooltip]")) {
  Tooltip.getOrCreateInstance(element)
}

for (const element of document.querySelectorAll(".alert")) {
  Alert.getOrCreateInstance(element)
}

for (const element of document.querySelectorAll("[data-bs-toggle=popover]")) {
  Popover.getOrCreateInstance(element)
}
