import { afterEach, expect, test } from "bun:test"
import { JSDOM, VirtualConsole } from "jsdom"

const jsdomErrors: unknown[] = []
const virtualConsole = new VirtualConsole()
virtualConsole.on("jsdomError", (error: unknown) => {
  jsdomErrors.push(error)
})

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
  pretendToBeVisual: true,
  virtualConsole,
})

const { window } = dom
Object.assign(globalThis, {
  window,
  document: window.document,
  navigator: window.navigator,
  Event: window.Event,
  CustomEvent: window.CustomEvent,
  EventTarget: window.EventTarget,
  Node: window.Node,
  Element: window.Element,
  HTMLElement: window.HTMLElement,
  HTMLAnchorElement: window.HTMLAnchorElement,
  Document: window.Document,
  DocumentFragment: window.DocumentFragment,
  ShadowRoot: window.ShadowRoot,
  SVGElement: window.SVGElement,
  MutationObserver: window.MutationObserver,
  getComputedStyle: window.getComputedStyle.bind(window),
})

const { showEditHelpTooltip } = await import("./_edit-help-tooltip.ts")
const { Tooltip } = await import("bootstrap")

const createEditLink = () => {
  const link = document.createElement("a")
  link.href = "/edit"
  link.textContent = "Edit"
  document.body.append(link)
  return link
}

/** Run Bootstrap transition timers inline and collect callback failures. */
const captureTransitionErrors = (run: () => void) => {
  const errors: unknown[] = []
  const queue: (() => void)[] = []
  const originalSetTimeout = globalThis.setTimeout

  globalThis.setTimeout = ((
    handler: TimerHandler,
    timeout?: number,
    ...args: unknown[]
  ) => {
    if (typeof handler !== "function") return originalSetTimeout(handler, timeout)
    queue.push(() => {
      Reflect.apply(handler, undefined, args)
    })
    return 0
  }) as typeof setTimeout

  try {
    run()
    while (queue.length > 0) {
      const runTimer = queue.shift()
      if (!runTimer) break
      try {
        runTimer()
      } catch (error) {
        errors.push(error)
      }
    }
  } finally {
    globalThis.setTimeout = originalSetTimeout
  }

  errors.push(...jsdomErrors)
  jsdomErrors.length = 0
  return errors
}

const expectDismissed = (link: HTMLAnchorElement) => {
  expect(link.hasAttribute("aria-describedby")).toBe(false)
  expect(document.querySelector(".tooltip")).toBeNull()
  expect(Tooltip.getInstance(link)).toBeNull()
}

afterEach(() => {
  jsdomErrors.length = 0
  document.body.replaceChildren()
})

test("dismissing after shown.bs.tooltip leaves no aria-describedby", async () => {
  const link = createEditLink()
  const shown = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("shown.bs.tooltip did not fire")),
      1000,
    )
    link.addEventListener(
      "shown.bs.tooltip",
      () => {
        clearTimeout(timer)
        resolve()
      },
      { once: true },
    )
  })

  const dispose = showEditHelpTooltip(link, "Edit help")
  await shown

  const errors = captureTransitionErrors(dispose)
  expect(errors).toEqual([])
  expectDismissed(link)
})

test("dismissing while the tooltip is still opening leaves no aria-describedby", () => {
  const link = createEditLink()

  const errors = captureTransitionErrors(() => {
    const dispose = showEditHelpTooltip(link, "Edit help")
    dispose()
  })

  expect(errors).toEqual([])
  expectDismissed(link)
})
