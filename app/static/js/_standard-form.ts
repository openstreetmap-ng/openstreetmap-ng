import { Alert } from "bootstrap"
import i18next from "i18next"

export interface APIDetail {
    type: "success" | "info" | "error"
    loc: [any, string]
    msg: string
}

/**
 * Initialize a standard bootstrap form
 * @see https://getbootstrap.com/docs/5.3/forms/validation/
 */
export const configureStandardForm = (
    form: HTMLFormElement,
    successCallback?: (data: any) => void,
    clientValidationCallback?: (form: HTMLFormElement) => string | APIDetail[] | null,
    options?: { formAppend: boolean },
): void => {
    console.debug("Initializing standard form", form)
    const submitElements = form.querySelectorAll("[type=submit]") as NodeListOf<HTMLInputElement | HTMLButtonElement>

    /** Set availability of submit elements */
    const toggleSubmit = (enabled: boolean): void => {
        console.debug("configureStandardForm", "toggleSubmit", enabled)
        for (const submit of submitElements) submit.disabled = !enabled
    }

    /** Handle feedback for a specific element */
    const handleElementFeedback = (element: Element, type: "success" | "info" | "error", message: string): void => {
        element.parentElement.classList.add("position-relative")

        let feedback = element.nextElementSibling
        if (!feedback?.classList.contains("element-feedback")) {
            feedback = document.createElement("div")
            feedback.classList.add("element-feedback")
            element.after(feedback)
        }

        if (type === "success" || type === "info") {
            feedback.classList.add("valid-tooltip")
            feedback.classList.remove("invalid-tooltip")
            element.classList.add("is-valid")
            element.classList.remove("is-invalid")
        } else {
            feedback.classList.add("invalid-tooltip")
            feedback.classList.remove("valid-tooltip")
            element.classList.add("is-invalid")
            element.classList.remove("is-valid")
        }

        feedback.textContent = message

        // Remove feedback on change or submit
        const onInput = () => {
            if (!feedback) return
            console.debug("Invalidating form feedback")
            form.dispatchEvent(new CustomEvent("invalidate"))
        }

        const onInvalidated = () => {
            if (!feedback) return
            console.debug("configureStandardForm", "handleElementFeedback", "onInvalidated")
            feedback.remove()
            feedback = null
            element.classList.remove("is-valid", "is-invalid")
        }

        // Listen for events that invalidate the feedback
        element.addEventListener("input", onInput, { once: true })
        form.addEventListener("invalidate", onInvalidated, { once: true })
        form.addEventListener("submit", onInvalidated, { once: true })
    }

    /** Handle feedback for the entire form */
    const handleFormFeedback = (type: "success" | "info" | "error", message: string): void => {
        let feedback = form.querySelector(".form-feedback")
        let feedbackAlert: Alert | null = null

        if (!feedback) {
            feedback = document.createElement("div")
            feedback.classList.add("form-feedback", "alert", "alert-dismissible", "fade", "show")
            feedback.role = "alert"
            const span = document.createElement("span")
            feedback.append(span)
            const closeButton = document.createElement("button")
            closeButton.type = "button"
            closeButton.classList.add("btn-close")
            closeButton.ariaLabel = i18next.t("javascripts.close")
            closeButton.dataset.bsDismiss = "alert"
            feedback.append(closeButton)
            feedbackAlert = new Alert(feedback)
            if (options?.formAppend) {
                feedback.classList.add("alert-last")
                form.append(feedback)
            } else {
                form.prepend(feedback)
            }
        }

        if (type === "success") {
            feedback.classList.remove("alert-info", "alert-danger")
            feedback.classList.add("alert-success")
        } else if (type === "info") {
            feedback.classList.remove("alert-success", "alert-danger")
            feedback.classList.add("alert-info")
        } else {
            feedback.classList.remove("alert-success", "alert-info")
            feedback.classList.add("alert-danger")
        }

        feedback.firstElementChild.textContent = message

        // Remove feedback on submit
        const onInvalidated = () => {
            if (!feedback) return
            console.debug("configureStandardForm", "handleFormFeedback", "onInvalidated")
            feedbackAlert.dispose()
            feedbackAlert = null
            feedback.remove()
            feedback = null
        }

        // Listen for events that invalidate the feedback
        form.addEventListener("invalidate", onInvalidated, { once: true })
        form.addEventListener("submit", onInvalidated, { once: true })
    }

    const processFormFeedback = (detail: string | APIDetail[]): void => {
        console.debug("Received form feedback", detail)

        if (Array.isArray(detail)) {
            // Process array of details
            for (const {
                type,
                loc: [_, field],
                msg,
            } of detail) {
                if (field) {
                    const input = form.elements.namedItem(field)
                    if (!(input instanceof HTMLInputElement) || input.type === "hidden") {
                        handleFormFeedback(type, msg)
                    } else {
                        handleElementFeedback(input, type, msg)
                    }
                } else {
                    handleFormFeedback(type, msg)
                }
            }
        } else {
            // Process detail as a single text message
            handleFormFeedback("error", detail)
        }
    }

    // Disable browser validation in favor of bootstrap
    form.noValidate = true
    form.classList.add("needs-validation")

    // On form submit, build and submit the request
    form.addEventListener("submit", (e: SubmitEvent): void => {
        console.debug("configureStandardForm", "onSubmit", form.action)
        e.preventDefault()

        // Check form validity
        if (!form.checkValidity()) {
            e.stopPropagation()
            form.classList.add("was-validated")
            return
        }

        form.classList.remove("was-validated")

        // Prevent double submission
        if (form.classList.contains("pending")) {
            console.info("Form already pending", form)
            return
        }

        if (clientValidationCallback) {
            const clientValidationResult = clientValidationCallback(form)
            if (
                clientValidationResult &&
                (!Array.isArray(clientValidationResult) || clientValidationResult.length > 0)
            ) {
                console.debug("Client validation failed")
                processFormFeedback(clientValidationResult)
                return
            }
        }

        form.classList.add("pending")
        toggleSubmit(false)

        fetch(form.action, {
            method: form.method,
            body: new FormData(form),
            mode: "same-origin",
            cache: "no-store",
            priority: "high",
        })
            .then(async (resp) => {
                if (resp.ok) console.debug("Form submitted successfully")

                // Attempt to parse response as JSON
                let data: any
                const contentType = resp.headers.get("Content-Type")
                if (contentType?.startsWith("application/json")) {
                    console.debug("Reading JSON response")
                    data = await resp.json()
                } else {
                    console.debug("Reading text response")
                    data = { detail: await resp.text() }
                }

                // Process form feedback if present
                const detail = data.detail
                if (detail) processFormFeedback(detail)

                // If the request was successful, call the callback
                if (resp.ok && successCallback) successCallback(data)
            })
            .catch((error) => {
                console.error("Failed to submit standard form", error)
                handleFormFeedback("error", error.message)
            })
            .finally(() => {
                form.classList.remove("pending")
                toggleSubmit(true)
            })
    })
}
