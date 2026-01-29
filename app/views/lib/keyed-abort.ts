import { type ReadonlySignal, signal } from "@preact/signals"

export type KeyedAbort = Readonly<{
  pending: ReadonlySignal<boolean>
  abort: () => void
  start: (nextKey: string) => KeyedAbortToken | null
}>

export type KeyedAbortToken = Readonly<{
  signal: AbortSignal
  done: () => void
}>

export const createKeyedAbort = (): KeyedAbort => {
  const pending = signal(false)
  let currentKey: string | null = null
  let currentController: AbortController | null = null

  const abort = () => {
    currentController?.abort()
    currentController = null
    currentKey = null
    pending.value = false
  }

  const start = (nextKey: string): KeyedAbortToken | null => {
    if (currentKey === nextKey) return null

    currentController?.abort()
    const controller = new AbortController()
    currentController = controller
    currentKey = nextKey
    pending.value = true

    return {
      signal: controller.signal,
      done: () => {
        if (currentController !== controller) return
        currentController = null
        currentKey = null
        pending.value = false
      },
    }
  }

  return { pending, abort, start }
}
