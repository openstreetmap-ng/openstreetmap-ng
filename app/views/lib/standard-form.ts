import type { Message } from "@bufbuild/protobuf"
import { fromBinary } from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
import {
  appendPasswordsToFormData,
  configurePasswordsForm,
  handlePasswordSchemaFeedback,
} from "@lib/password-hash"
import { batch } from "@preact/signals"
import { assertExists, assertFalse, unreachable } from "@std/assert"
import { parseMediaType } from "@std/media-types/parse-media-type"
import { Alert } from "bootstrap"
import { t } from "i18next"

export interface APIDetail {
  type: "success" | "info" | "error"
  loc: [string | null, string | null]
  msg: string
}

/**
 * Initialize a standard bootstrap form
 * @see https://getbootstrap.com/docs/5.3/forms/validation/
 */
export const configureStandardForm = <T = any>(
  form: HTMLFormElement | null,
  successCallback?: (data: T, headers: Headers) => void,
  options?: {
    formBody?: Element
    formAppend?: boolean
    cancelOnSubmit?: boolean
    removeEmptyFields?: boolean
    protobuf?: GenMessage<T & Message>
    validationCallback?: (
      formData: FormData,
    ) => Promise<string | APIDetail[] | null> | string | APIDetail[] | null
    errorCallback?: (error: Error) => void
  },
): void | (() => void) => {
  if (!form || form.classList.contains("needs-validation")) return
  let formAction = form.getAttribute("action") ?? ""
  console.debug("StandardForm: Initializing", formAction)

  // Disable browser validation in favor of bootstrap
  // disables maxlength and other browser checks: form.noValidate = true
  form.classList.add("needs-validation")

  const {
    formBody = form,
    formAppend = false,
    cancelOnSubmit = false,
    removeEmptyFields = false,
    protobuf,
    validationCallback,
    errorCallback,
  } = options ?? {}

  const submitElements = form.querySelectorAll<HTMLInputElement | HTMLButtonElement>(
    "[type=submit]",
  )
  const passwordInputs = form.querySelectorAll("input[type=password][data-name]")
  if (passwordInputs.length) configurePasswordsForm(form, passwordInputs)
  let abortController = new AbortController()

  const setPendingState = (state: boolean) => {
    const currentState = form.classList.contains("pending")
    if (currentState === state) return
    console.debug("StandardForm: Pending state", state, formAction)
    if (state) {
      form.classList.add("pending")
      for (const submit of submitElements) submit.disabled = true
    } else {
      form.classList.remove("pending")
      for (const submit of submitElements) submit.disabled = false
    }
  }

  const handleElementFeedback = (
    element: HTMLInputElement | HTMLTextAreaElement,
    type: "success" | "info" | "error",
    message: string,
  ) => {
    if (element.classList.contains("hidden-password-input")) {
      const actualElement = form.querySelector(
        `input[type=password][data-name="${element.name}"]`,
      )
      if (actualElement) {
        handleElementFeedback(actualElement, type, message)
        return
      }
    }

    element.parentElement!.classList.add("position-relative")

    let feedback = element.nextElementSibling
    if (!feedback?.classList.contains("element-feedback")) {
      feedback = document.createElement("div")
      feedback.classList.add("element-feedback")
      element.after(feedback)
    }

    const isValid = type === "success" || type === "info"
    feedback.classList.toggle("valid-tooltip", isValid)
    feedback.classList.toggle("invalid-tooltip", !isValid)
    element.classList.toggle("is-valid", isValid)
    element.classList.toggle("is-invalid", !isValid)

    feedback.textContent = message

    // Clear stale validation when user modifies input
    const onInput = () => {
      if (!feedback) return
      form.dispatchEvent(new CustomEvent("invalidate"))
    }

    const onInvalidated = () => {
      if (!feedback) return
      feedback.remove()
      feedback = null
      element.classList.remove("is-valid", "is-invalid")
    }

    element.addEventListener("input", onInput, { once: true })
    form.addEventListener("invalidate", onInvalidated, { once: true })
    form.addEventListener("submit", onInvalidated, { once: true })
  }

  /** Handle feedback for the entire form */
  const handleFormFeedback = (
    type: "success" | "info" | "error" | "missing",
    message: string,
    after?: HTMLElement,
  ) => {
    if (!message) return

    let feedback = form.querySelector(".form-feedback")
    let feedbackAlert: Alert | null = null

    if (!feedback) {
      feedback = document.createElement("div")
      feedback.classList.add(
        "form-feedback",
        "alert",
        "alert-dismissible",
        "fade",
        "show",
      )
      feedback.role = "alert"
      const span = document.createElement("span")
      feedback.append(span)
      const closeButton = document.createElement("button")
      closeButton.type = "button"
      closeButton.classList.add("btn-close")
      closeButton.ariaLabel = t("javascripts.close")
      closeButton.dataset.bsDismiss = "alert"
      feedback.append(closeButton)
      feedbackAlert = new Alert(feedback)

      if (after) {
        feedback.classList.add("alert-inner")
        after.after(feedback)
      } else if (formAppend) {
        const scrollContainer = findScrollableContainer(formBody)
        const scrollWindow = scrollContainer === document.documentElement

        // Preserve scroll position for auto-scroll UX
        let wasAtBottom: boolean
        if (scrollWindow) {
          wasAtBottom =
            window.innerHeight + window.scrollY >= document.body.offsetHeight - 20
        } else {
          const { scrollTop, scrollHeight, clientHeight } = scrollContainer
          wasAtBottom = scrollTop + clientHeight >= scrollHeight - 20
        }

        feedback.classList.add("alert-last")
        formBody.append(feedback)

        // Keep latest content visible if user was at bottom
        if (wasAtBottom && scrollWindow) {
          window.scrollTo({
            top: document.body.scrollHeight,
            behavior: "smooth",
          })
        } else if (wasAtBottom) {
          scrollContainer.scrollTo({
            top: scrollContainer.scrollHeight,
            behavior: "smooth",
          })
        }
      } else {
        formBody.prepend(feedback)
      }
    }

    feedback.classList.toggle("alert-success", type === "success")
    feedback.classList.toggle("alert-info", type === "info")
    feedback.classList.toggle("alert-danger", type === "error" || type === "missing")

    feedback.firstElementChild!.textContent = message

    // Remove feedback on submit
    const onInvalidated = () => {
      if (!feedback) return
      assertExists(feedbackAlert)
      feedbackAlert.dispose()
      feedbackAlert = null
      feedback.remove()
      feedback = null
    }

    form.addEventListener("invalidate", onInvalidated, { once: true })
    form.addEventListener("submit", onInvalidated, { once: true })
  }

  const processFormFeedback = (detail: string | APIDetail[]) => {
    console.debug("StandardForm: Received feedback", formAction, detail)
    if (!Array.isArray(detail)) {
      handleFormFeedback("error", detail)
      return
    }

    for (const {
      type,
      loc: [_, field],
      msg,
    } of detail) {
      if (!field) {
        handleFormFeedback(type, msg)
        continue
      }

      const input = form.querySelector(`[name="${field}"]`)
      console.debug("StandardForm: Processing field feedback", field, type)

      if (
        !(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)
      ) {
        handleFormFeedback(type, msg)
        continue
      }

      if (input.type === "hidden") {
        if (passwordInputs.length && input.name === "password_schema") {
          if (handlePasswordSchemaFeedback(form, msg)) {
            setPendingState(false)
            form.requestSubmit()
          }
          continue
        }

        handleFormFeedback(type, msg, input)
        continue
      }

      handleElementFeedback(input, type, msg)
    }
  }

  const onSubmit = async (e: SubmitEvent) => {
    console.debug("StandardForm: Submit", formAction)
    e.preventDefault()

    // Stage 1: Validate form structure
    if (!form.checkValidity()) {
      e.stopPropagation()
      form.classList.add("was-validated")
      return
    }
    form.classList.remove("was-validated")

    // Stage 2: Handle concurrent submissions
    if (cancelOnSubmit) {
      abortController.abort()
      abortController = new AbortController()
    } else if (form.classList.contains("pending")) {
      console.debug("StandardForm: Already pending, ignoring submit", formAction)
      return
    }
    const currentAbortController = abortController

    // Stage 3: Serialize form data
    setPendingState(true)
    const formData = new FormData(form)

    if (passwordInputs.length)
      await appendPasswordsToFormData(form, formData, passwordInputs)

    formAction = form.getAttribute("action") ?? ""
    const method = form.method.toUpperCase()
    let url: string
    let body: BodyInit | null = null

    if (method === "POST") {
      url = formAction
      body = formData
      if (removeEmptyFields) {
        const keysToDelete: string[] = []
        for (const [key, value] of body.entries()) {
          if (typeof value === "string" && !value) {
            keysToDelete.push(key)
          }
        }
        for (const key of keysToDelete) {
          body.delete(key)
        }
      }
    } else if (method === "GET") {
      const params = new URLSearchParams()
      for (const [key, value] of formData.entries()) {
        const valueString = value.toString()
        if (removeEmptyFields && !valueString) continue
        params.append(key, valueString)
      }
      url = `${formAction}?${params}`
    } else {
      unreachable(`Unsupported standard form method ${method}`)
    }

    // Stage 4: Run client-side validation
    if (validationCallback) {
      let result = batch(() => validationCallback(formData))
      if (result instanceof Promise) {
        result = await result
      }
      if (typeof result === "string" || (Array.isArray(result) && result.length > 0)) {
        console.debug("StandardForm: Client validation failed", formAction)
        processFormFeedback(result)
        setPendingState(false)
        return
      }
    }

    // Stage 5: Execute request and handle response
    try {
      const resp = await fetch(url, {
        method,
        body,
        signal: cancelOnSubmit ? currentAbortController.signal : null,
        priority: "high",
      })

      let contentType = resp.headers.get("Content-Type") ?? ""
      if (contentType) contentType = parseMediaType(contentType)[0]
      const isJson = contentType === "application/json" || contentType.endsWith("+json")
      const isProtobuf = contentType === "application/x-protobuf"
      assertFalse(
        resp.ok && contentType && Boolean(protobuf) !== isProtobuf,
        `Mismatched response content type: ${contentType}`,
      )

      let data: any = null
      if (isJson) {
        data = await resp.json()
      } else if (isProtobuf) {
        data = fromBinary(protobuf!, new Uint8Array(await resp.arrayBuffer()))
      } else if (contentType) {
        data = { detail: await resp.text() }
      }
      currentAbortController.signal.throwIfAborted()

      // Process form feedback if present
      const detail = data?.detail ?? ""
      if (detail) processFormFeedback(detail)

      // If the request was successful, call the callback
      batch(() => {
        if (resp.ok) {
          successCallback?.(data, resp.headers)
        } else {
          errorCallback?.(new Error(detail))
        }
      })

      setPendingState(false)
    } catch (error) {
      if (error.name === "AbortError") return
      console.error("StandardForm: Submit failed", formAction, error)
      handleFormFeedback("error", error.message)

      batch(() => {
        errorCallback?.(error)
      })

      setPendingState(false)
    }
  }
  form.addEventListener("submit", onSubmit)

  return () => {
    console.debug("StandardForm: Disposing", formAction)
    abortController.abort()
    form.dispatchEvent(new CustomEvent("invalidate"))
    form.removeEventListener("submit", onSubmit)
    form.classList.remove("needs-validation", "was-validated", "pending")
  }
}

/** Find the scrollable container for the form */
const findScrollableContainer = (element: Element) => {
  let current = element.parentElement
  while (current && current !== document.body) {
    const style = window.getComputedStyle(current)
    const overflowY = style.overflowY
    if (overflowY === "auto" || overflowY === "scroll") {
      return current
    }
    current = current.parentElement
  }
  // Fallback to window/document if no scrollable container found
  return document.documentElement
}
