import type {
  DescMessage,
  DescMethodUnary,
  MessageInitShape,
  MessageValidType,
} from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
import { type CallOptions, ConnectError } from "@connectrpc/connect"
import {
  createDisposeScope,
  type DisposeScope,
  useDisposeEffect,
} from "@lib/dispose-scope"
import {
  appendPasswordsToFormData,
  configurePasswordsForm,
  handlePasswordSchemaFeedback,
} from "@lib/password-hash"
import {
  type StandardFeedbackDetail,
  type StandardFeedbackDetail_Entry,
  StandardFeedbackDetail_Severity,
} from "@lib/proto/shared_pb"
import {
  connectErrorToMessage,
  connectErrorToStandardFeedback,
  fromBinaryValid,
  rpcClient,
} from "@lib/rpc"
import { batch, effect, useSignal } from "@preact/signals"
import { assertExists, assertFalse, unreachable } from "@std/assert"
import { parseMediaType } from "@std/media-types/parse-media-type"
import { Alert } from "bootstrap"
import { t } from "i18next"
import type { ComponentChildren, Ref } from "preact"
import { useEffect, useRef } from "preact/hooks"

export interface APIDetail {
  type: "success" | "info" | "error"
  loc: [string | null, string | null]
  msg: string
}

type ValidationResult = string | APIDetail[] | null

const createStandardFormFeedbackRenderer = (
  form: HTMLFormElement,
  scope: DisposeScope,
  options?: {
    formBody?: Element
    formAppend?: boolean
    onHiddenInputFeedback?: (ctx: {
      input: HTMLInputElement
      type: APIDetail["type"]
      message: string
    }) => boolean
  },
) => {
  const { formBody = form, formAppend = false, onHiddenInputFeedback } = options ?? {}

  const handleElementFeedback = (
    element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
    type: APIDetail["type"],
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

    scope.dom(element, "input", onInput, { once: true })
    scope.dom(form, "invalidate", onInvalidated, { once: true })
    scope.dom(form, "submit", onInvalidated, { once: true })
  }

  const handleFormFeedback = (
    type: APIDetail["type"] | "missing",
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
          window.scrollTo({ top: document.body.scrollHeight })
        } else if (wasAtBottom) {
          scrollContainer.scrollTo({ top: scrollContainer.scrollHeight })
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

    scope.dom(form, "invalidate", onInvalidated, { once: true })
    scope.dom(form, "submit", onInvalidated, { once: true })
  }

  const processFormFeedback = (
    detail: string | (APIDetail | StandardFeedbackDetail_Entry)[],
  ) => {
    console.debug("StandardForm: Received feedback", detail)
    if (!Array.isArray(detail)) {
      handleFormFeedback("error", detail)
      return
    }

    for (const entry of detail) {
      const { type, field, msg } =
        "loc" in entry
          ? { type: entry.type, field: entry.loc[1], msg: entry.msg }
          : {
              type: StandardFeedbackDetail_Severity[
                entry.severity
              ] as keyof typeof StandardFeedbackDetail_Severity,
              field: entry.field ?? null,
              msg: entry.message,
            }

      if (!field) {
        handleFormFeedback(type, msg)
        continue
      }

      const queryInput = (
        name: string,
      ): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null =>
        form.querySelector(
          `input[name="${name}"], textarea[name="${name}"], select[name="${name}"]`,
        ) ?? (name.includes(".") ? queryInput(name.split(".", 1)[0]) : null)

      const input = queryInput(field)
      console.debug("StandardForm: Processing field feedback", field, type)

      if (!input) {
        handleFormFeedback(type, msg)
        continue
      }

      if (input instanceof HTMLInputElement && input.type === "hidden") {
        if (onHiddenInputFeedback?.({ input, type, message: msg })) continue
        handleFormFeedback(type, msg, input)
        continue
      }

      handleElementFeedback(input, type, msg)
    }
  }

  return { handleFormFeedback, handleElementFeedback, processFormFeedback }
}

/** Find the scrollable container for the form */
const findScrollableContainer = (element: Node) => {
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
    cancelOnValidationChange?: boolean
    removeEmptyFields?: boolean
    protobuf?: GenMessage<any, { validType: T }>
    validationCallback?: (
      formData: FormData,
    ) => Promise<ValidationResult> | ValidationResult
    errorCallback?: (error: Error) => void
  },
): (() => void) | void => {
  if (!form || form.classList.contains("needs-validation")) return
  let formAction = form.getAttribute("action") ?? ""
  console.debug("StandardForm: Initializing", formAction)

  const scope = createDisposeScope()

  // Disable browser validation in favor of bootstrap
  // disables maxlength and other browser checks: form.noValidate = true
  form.classList.add("needs-validation")
  scope.defer(() =>
    form.classList.remove("needs-validation", "was-validated", "pending"),
  )

  const {
    formBody = form,
    formAppend = false,
    cancelOnValidationChange = false,
    removeEmptyFields = false,
    protobuf,
    validationCallback,
    errorCallback,
  } = options ?? {}

  const submitElements = form.querySelectorAll(
    "button[type=submit], input[type=submit]",
  )
  const passwordInputs = form.querySelectorAll("input[type=password][data-name]")
  if (passwordInputs.length) configurePasswordsForm(form, passwordInputs)

  let abortController = new AbortController()
  scope.defer(() => abortController.abort())

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

  const { handleFormFeedback, processFormFeedback } =
    createStandardFormFeedbackRenderer(form, scope, {
      formBody,
      formAppend,
      onHiddenInputFeedback: ({ input, message }) => {
        if (passwordInputs.length && input.name === "password_schema") {
          if (handlePasswordSchemaFeedback(form, message)) {
            setPendingState(false)
            form.requestSubmit()
          }
          return true
        }
        return false
      },
    })

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
    if (cancelOnValidationChange) {
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
        for (const [key, value] of formData.entries()) {
          if (typeof value === "string" && !value) {
            keysToDelete.push(key)
          }
        }
        for (const key of keysToDelete) {
          formData.delete(key)
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
    let disposeValidationEffect: (() => void) | undefined
    if (validationCallback) {
      let result: Promise<ValidationResult> | ValidationResult | undefined
      disposeValidationEffect = effect(() => {
        if (result === undefined) {
          result = validationCallback(formData)
        } else if (cancelOnValidationChange) {
          currentAbortController.abort()
          disposeValidationEffect!()
          disposeValidationEffect = undefined
        }
      })

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
        signal: cancelOnValidationChange ? currentAbortController.signal : null,
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
        data = fromBinaryValid(protobuf!, new Uint8Array(await resp.arrayBuffer()))
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
    } finally {
      disposeValidationEffect?.()
    }
  }
  scope.dom(form, "submit", onSubmit)
  scope.defer(() => form.dispatchEvent(new CustomEvent("invalidate")))

  return scope.dispose
}

interface StandardFormProps<I extends DescMessage, O extends DescMessage> {
  method: DescMethodUnary<I, O>
  buildRequest: (
    ctx: Readonly<{
      form: HTMLFormElement
      formData: FormData
      submitter: HTMLButtonElement | HTMLInputElement | null
      signal: AbortSignal
    }>,
  ) => MessageInitShape<I> | Promise<MessageInitShape<I>>
  onSuccess?: (
    resp: MessageValidType<O>,
    ctx: Readonly<{
      form: HTMLFormElement
      submitter: HTMLButtonElement | HTMLInputElement | null
      signal: AbortSignal
      request: MessageInitShape<I>
    }>,
  ) => void
  onError?: (
    err: ConnectError,
    ctx: Readonly<{
      form: HTMLFormElement
      submitter: HTMLButtonElement | HTMLInputElement | null
      signal: AbortSignal
      request: MessageInitShape<I>
    }>,
  ) => void
  concurrency?: "ignore" | "restart"
  abortKey?: unknown
  resetOnSuccess?: boolean
  feedbackRoot?: Element
  feedbackRootSelector?: string
  formRef?: Ref<HTMLFormElement>
  class?: string
  children: ComponentChildren
}

export const StandardForm = <I extends DescMessage, O extends DescMessage>({
  method,
  buildRequest,
  onSuccess,
  onError,
  concurrency = "ignore",
  abortKey,
  resetOnSuccess = false,
  feedbackRoot,
  feedbackRootSelector,
  formRef,
  class: className,
  children,
}: StandardFormProps<I, O>) => {
  const innerFormRef = useRef<HTMLFormElement>(null)
  const feedbackRef = useRef<ReturnType<
    typeof createStandardFormFeedbackRenderer
  > | null>(null)

  const isPending = useSignal(false)
  const isValidated = useSignal(false)
  const abortControllerRef = useRef<AbortController>(new AbortController())

  useDisposeEffect((scope) => {
    const form = innerFormRef.current
    if (!form) return

    const feedback = createStandardFormFeedbackRenderer(form, scope, {
      formBody:
        feedbackRoot ??
        (feedbackRootSelector ? form.querySelector(feedbackRootSelector) : null) ??
        form,
    })
    feedbackRef.current = feedback

    return () => {
      abortControllerRef.current.abort()
      isPending.value = false
      form.dispatchEvent(new CustomEvent("invalidate"))
      feedbackRef.current = null
    }
  }, [])

  // Effect: abort inflight request if caller changes the abortKey
  useEffect(() => {
    if (concurrency !== "restart") return
    if (!isPending.value) return

    abortControllerRef.current.abort()
    abortControllerRef.current = new AbortController()
    isPending.value = false
    isValidated.value = false
  }, [abortKey, concurrency])

  const onSubmit = async (ev: SubmitEvent) => {
    const form = innerFormRef.current
    const feedback = feedbackRef.current
    if (!(form && feedback)) return

    ev.preventDefault()

    // Stage 1: Validate form structure
    if (!form.checkValidity()) {
      ev.stopPropagation()
      isValidated.value = true
      return
    }
    isValidated.value = false

    // Stage 2: Handle concurrent submissions
    if (concurrency !== "restart" && isPending.value) {
      console.debug("StandardForm: Already pending, ignoring submit")
      return
    }

    if (isPending.value) abortControllerRef.current.abort()
    const abortController = new AbortController()
    abortControllerRef.current = abortController
    isPending.value = true

    // Stage 3: Snapshot form data + build request
    const submitter =
      ev.submitter instanceof HTMLButtonElement ||
      ev.submitter instanceof HTMLInputElement
        ? ev.submitter
        : null

    const formData = new FormData(form, submitter)

    let request: MessageInitShape<I>
    try {
      request = await buildRequest({
        form,
        formData,
        submitter,
        signal: abortController.signal,
      })
    } catch (error) {
      if (abortController.signal.aborted) return
      console.error("StandardForm: buildRequest failed", error)
      feedback.handleFormFeedback("error", error.message)
      isPending.value = false
      return
    }

    const ctx = {
      form,
      submitter,
      signal: abortController.signal,
      request,
    }

    // Stage 4: Execute RPC request and handle response
    try {
      const fn = rpcClient(method.parent)[method.localName] as (
        request: MessageInitShape<I>,
        options?: CallOptions,
      ) => Promise<MessageValidType<O>>

      const response = await fn(request, { signal: ctx.signal })

      if (resetOnSuccess) form.reset()

      // Allow responses to return feedback as StandardFeedbackDetail on a `feedback` field.
      if ("feedback" in response && "entries" in (response.feedback as any)) {
        const entries = (response.feedback as StandardFeedbackDetail).entries
        if (entries.length) feedback.processFormFeedback(entries)
      }

      onSuccess?.(response, ctx)
    } catch (error) {
      if (ctx.signal.aborted) return

      const err = ConnectError.from(error)
      const detail = connectErrorToStandardFeedback(err)
      if (detail) {
        feedback.processFormFeedback(detail)
      } else {
        feedback.handleFormFeedback("error", connectErrorToMessage(err))
      }

      onError?.(err, ctx)
    } finally {
      if (abortControllerRef.current === abortController) {
        isPending.value = false
      }
    }
  }

  return (
    <form
      ref={(el) => {
        innerFormRef.current = el
        if (typeof formRef === "function") {
          formRef(el)
        } else if (formRef) {
          formRef.current = el
        }
      }}
      class={`${className ?? ""} needs-validation ${isPending.value ? "pending" : ""} ${
        isValidated.value ? "was-validated" : ""
      }`}
      onSubmit={onSubmit}
    >
      <fieldset disabled={isPending.value}>{children}</fieldset>
    </form>
  )
}
