import { addMapLayer, type LayerId, removeMapLayer } from "@lib/map/layers/layers"
import {
  cancelAnimationFramePolyfill,
  requestAnimationFramePolyfill,
} from "@lib/polyfills"
import { useSignalEffect } from "@preact/signals"
import type { MapEventType, MapLayerEventType, Map as MaplibreMap } from "maplibre-gl"
import { useEffect } from "preact/hooks"

type Disposer = (() => void) | void
type DeferDisposer = Disposer | null | undefined

type DomBinder = {
  <K extends keyof WindowEventMap>(
    target: Window,
    type: K,
    listener: (event: WindowEventMap[K]) => void,
    options?: AddEventListenerOptions,
  ): DisposeScope
  <K extends keyof DocumentEventMap>(
    target: Document,
    type: K,
    listener: (event: DocumentEventMap[K]) => void,
    options?: AddEventListenerOptions,
  ): DisposeScope
  <K extends keyof HTMLElementEventMap>(
    target: HTMLElement,
    type: K,
    listener: (event: HTMLElementEventMap[K]) => void,
    options?: AddEventListenerOptions,
  ): DisposeScope
  (
    target: EventTarget,
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: AddEventListenerOptions,
  ): DisposeScope
}

export type Scheduled<F extends (...args: any[]) => void> = ((
  ...args: Parameters<F>
) => void) & {
  cancel: () => void
  flush: () => void
  pending: () => boolean
}

type FrameContext = Readonly<{
  time: DOMHighResTimeStamp
  startTime: DOMHighResTimeStamp
  next: () => void
}>

export type DisposeScope = Readonly<{
  signal: AbortSignal
  dispose: () => void

  child: () => DisposeScope
  defer: (dispose: DeferDisposer) => DisposeScope

  every: (ms: number, fn: () => void) => DisposeScope
  frame: <Args extends any[]>(
    fn: (ctx: FrameContext, ...args: Args) => void,
  ) => Scheduled<(...args: Args) => void>
  throttle: <F extends (...args: any[]) => void>(ms: number, fn: F) => Scheduled<F>

  dom: DomBinder

  map: <T extends keyof MapEventType>(
    map: MaplibreMap,
    type: T,
    listener: (ev: MapEventType[T] & object) => void,
  ) => DisposeScope

  mapLayerLifecycle: (
    map: MaplibreMap,
    layerId: LayerId,
    triggerEvent?: boolean,
  ) => DisposeScope

  mapLayer: <T extends keyof MapLayerEventType>(
    map: MaplibreMap,
    type: T,
    layerId: string | readonly string[],
    listener: (ev: MapLayerEventType[T] & object) => void,
  ) => DisposeScope
}>

export const createDisposeScope = (): DisposeScope => {
  let isDisposed = false
  const disposers: (() => void)[] = []
  const abortController = new AbortController()

  const dispose = () => {
    if (isDisposed) return
    isDisposed = true
    abortController.abort()

    for (let i = disposers.length - 1; i >= 0; i--) {
      try {
        disposers[i]()
      } catch (err) {
        console.error("DisposeScope: disposer threw", err)
      }
    }
  }

  const child = () => {
    const childScope = createDisposeScope()
    defer(childScope.dispose)
    return childScope
  }

  const defer = (disposer: DeferDisposer) => {
    if (typeof disposer !== "function") return scope
    if (isDisposed) {
      try {
        disposer()
      } catch (err) {
        console.error("DisposeScope: disposer threw", err)
      }
      return scope
    }
    disposers.push(disposer)
    return scope
  }

  const every = (ms: number, fn: () => void) => {
    if (isDisposed) return scope
    const id = window.setInterval(fn, ms)
    defer(() => window.clearInterval(id))
    return scope
  }

  const frame = <Args extends any[]>(
    fn: (ctx: FrameContext, ...args: Args) => void,
  ): Scheduled<(...args: Args) => void> => {
    let rafId: number | null = null
    let pendingArgs: Args | null = null
    let startTime: DOMHighResTimeStamp | null = null

    let scheduled: Scheduled<(...args: Args) => void>
    const run = (time: DOMHighResTimeStamp) => {
      if (isDisposed) return
      const args = pendingArgs!
      rafId = null
      pendingArgs = null
      startTime ??= time
      fn({ time, startTime, next: () => scheduled(...args) }, ...args)
      if (rafId === null) startTime = null
    }

    scheduled = ((...args: Args) => {
      pendingArgs = args
      rafId ??= requestAnimationFramePolyfill(run)
    }) as Scheduled<(...args: Args) => void>

    scheduled.cancel = () => {
      if (rafId === null) return
      cancelAnimationFramePolyfill(rafId)
      rafId = null
      pendingArgs = null
      startTime = null
    }

    scheduled.flush = () => {
      if (rafId === null) return
      cancelAnimationFramePolyfill(rafId)
      run(performance.now())
    }

    scheduled.pending = () => rafId !== null

    defer(scheduled.cancel)
    return scheduled
  }

  const throttle = <F extends (...args: any[]) => void>(
    ms: number,
    fn: F,
  ): Scheduled<F> => {
    let timeoutId: number | null = null
    let pendingArgs: Parameters<F> | null = null
    let lastInvoke = Number.NEGATIVE_INFINITY

    const clearTimeoutId = () => {
      if (timeoutId === null) return false
      window.clearTimeout(timeoutId)
      timeoutId = null
      return true
    }

    const run = () => {
      if (isDisposed) return
      const args = pendingArgs!
      pendingArgs = null
      lastInvoke = performance.now()
      fn(...args)
    }

    const scheduled = ((...args: Parameters<F>) => {
      pendingArgs = args

      const elapsed = performance.now() - lastInvoke
      const delta = ms - elapsed
      if (delta <= 0) {
        clearTimeoutId()
        run()
        return
      }

      timeoutId ??= window.setTimeout(() => {
        timeoutId = null
        run()
      }, delta)
    }) as Scheduled<F>

    scheduled.cancel = () => {
      if (clearTimeoutId()) pendingArgs = null
    }
    scheduled.flush = () => {
      if (clearTimeoutId()) run()
    }
    scheduled.pending = () => timeoutId !== null

    defer(scheduled.cancel)
    return scheduled
  }

  const dom: DomBinder = (
    target: EventTarget,
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: AddEventListenerOptions,
  ) => {
    if (isDisposed) return scope
    target.addEventListener(type, listener, {
      ...options,
      signal: abortController.signal,
    })
    return scope
  }

  const map: DisposeScope["map"] = (mapInstance, type, listener) => {
    if (isDisposed) return scope

    const subscription = mapInstance.on(type, listener)
    return defer(() => subscription.unsubscribe())
  }

  const mapLayerLifecycle = (
    map: MaplibreMap,
    layerId: LayerId,
    triggerEvent = true,
  ) => {
    if (isDisposed) return scope

    addMapLayer(map, layerId, triggerEvent)
    defer(() => removeMapLayer(map, layerId, triggerEvent))
    return scope
  }

  const mapLayer: DisposeScope["mapLayer"] = (mapInstance, type, layerId, listener) => {
    if (isDisposed) return scope

    if (typeof layerId === "string") {
      const subscription = mapInstance.on(type, layerId, listener)
      return defer(() => subscription.unsubscribe())
    }

    const subscription = mapInstance.on(type, layerId as string[], listener)
    return defer(() => subscription.unsubscribe())
  }

  const scope = {
    signal: abortController.signal,
    dispose,
    child,
    defer,
    every,
    frame,
    throttle,
    dom,
    map,
    mapLayerLifecycle,
    mapLayer,
  }
  return scope
}

export const useDisposeEffect = (
  setup: (scope: DisposeScope) => DeferDisposer,
  deps?: Parameters<typeof useEffect>[1],
) => {
  useEffect(() => {
    const scope = createDisposeScope()
    scope.defer(setup(scope))
    return scope.dispose
  }, deps)
}

export const useDisposeSignalEffect = (
  setup: (scope: DisposeScope) => DeferDisposer,
) => {
  useSignalEffect(() => {
    const scope = createDisposeScope()
    scope.defer(setup(scope))
    return scope.dispose
  })
}
