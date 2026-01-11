import { useSignal } from "@preact/signals"
import { delay } from "@std/async/delay"
import { SECOND } from "@std/datetime/constants"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { useId, useRef } from "preact/hooks"

const FEEDBACK_DURATION = 1.5 * SECOND

const copyFeedbackAbortMap = new WeakMap<HTMLElement, AbortController>()

const setIconState = (icon: HTMLElement | null, copied: boolean) => {
  if (!icon) return
  icon.classList.toggle("bi-copy", !copied)
  icon.classList.toggle("bi-check2", copied)
}

const runCopyFeedback = async (button: HTMLElement) => {
  const icon = button.querySelector("i")
  setIconState(icon, true)

  const prevAbort = copyFeedbackAbortMap.get(button)
  prevAbort?.abort()
  const abortController = new AbortController()
  copyFeedbackAbortMap.set(button, abortController)

  try {
    await delay(FEEDBACK_DURATION, { signal: abortController.signal })
  } catch {
    return
  }

  setIconState(icon, false)
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (error) {
    console.warn("Copy: Failed to copy", error)
    alert(error.message)
    return false
  }

  return true
}

export const configureCopyGroups = (root: ParentNode) => {
  const elements = root.querySelectorAll(".copy-group")
  console.debug("CopyGroup: Initializing", elements.length)

  for (const element of elements) {
    let button: HTMLElement
    let input: HTMLInputElement | null

    if (element.tagName === "BUTTON") {
      button = element as HTMLButtonElement
      input = null
    } else {
      button = element.querySelector("i.bi-copy")!.parentElement!
      input = element.querySelector("input.form-control")
    }

    input?.addEventListener("focus", input.select)

    button.addEventListener("click", async () => {
      input?.select()

      const text = input
        ? input.value
        : root.querySelector(button.dataset.copyTarget!)!.textContent.trim()

      const ok = await copyToClipboard(text)
      if (!ok) return

      await runCopyFeedback(button)
    })
  }
}

export const CopyField = ({
  label,
  value,
  inputClass,
}: {
  label: ComponentChildren
  value: string
  inputClass?: string
}) => {
  const copied = useSignal(false)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const inputId = useId()
  const feedbackAbortRef = useRef<AbortController | null>(null)

  const onCopy = async () => {
    inputRef.current?.select()
    const ok = await copyToClipboard(value)
    if (!ok) return

    copied.value = true
    feedbackAbortRef.current?.abort()
    feedbackAbortRef.current = new AbortController()

    try {
      await delay(FEEDBACK_DURATION, { signal: feedbackAbortRef.current.signal })
    } catch {
      return
    }

    copied.value = false
  }

  return (
    <div class="custom-input-group mb-2">
      <label for={inputId}>{label}</label>
      <div class="input-group">
        <input
          id={inputId}
          class={`form-control ${inputClass ?? ""}`}
          type="text"
          autoComplete="off"
          readOnly
          value={value}
          ref={(el) => {
            inputRef.current = el
          }}
          onFocus={(e) => e.currentTarget.select()}
        />
        <button
          class="btn btn-primary"
          type="button"
          title={t("action.copy")}
          onClick={onCopy}
        >
          <i class={`bi ${copied.value ? "bi-check2" : "bi-copy"}`}></i>
        </button>
      </div>
    </div>
  )
}

// Initialize on load (legacy DOM-enhanced usage)
configureCopyGroups(document.body)
