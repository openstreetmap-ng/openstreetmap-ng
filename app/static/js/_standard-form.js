import { Alert } from "bootstrap"

/**
 * Initialize a standard bootstrap form
 * @param {HTMLFormElement} form The form element to initialize
 * @param {object} options
 * @param {function|null} options.successCallback Optional callback to call on success
 * @returns {void}
 * @see https://getbootstrap.com/docs/5.3/forms/validation/
 */
export const configureStandardForm = (form, { successCallback = null }) => {
    console.debug("Initializing standard form", form)

    const submitElements = form.querySelectorAll("[type=submit]")

    /**
     * Set availability of submit elements
     * @param {boolean} enabled Whether the submit buttons should be enabled
     * @returns {void}
     */
    const toggleSubmit = (enabled) => {
        for (const submit of submitElements) {
            submit.disabled = !enabled
        }
    }

    /**
     * Handle feedback for a specific element
     * @param {HTMLElement} element
     * @param {"success"|"info"|"error"} type
     * @param {string} message
     * @returns {void}
     */
    const handleElementFeedback = (element, type, message) => {
        let feedback = element.nextElementSibling
        if (!feedback?.classList.contains("element-feedback")) {
            feedback = document.createElement("div")
            feedback.classList.add("element-feedback")
            element.after(feedback)
        }

        if (type === "success" || type === "info") {
            feedback.classList.add("valid-feedback")
            feedback.classList.remove("invalid-feedback")
        } else if (type === "error") {
            feedback.classList.add("invalid-feedback")
            feedback.classList.remove("valid-feedback")
        } else {
            console.error(`Unsupported feedback type: ${type}`)
            return
        }

        feedback.textContent = message

        // Remove feedback on change or submit
        const onInvalidated = () => {
            if (!feedback) return
            feedback.remove()
            feedback = null
            element.removeEventListener("change", onInvalidated)
            form.removeEventListener("submit", onInvalidated)
        }

        // Listen for events that invalidate the feedback
        element.addEventListener("change", onInvalidated)
        form.addEventListener("submit", onInvalidated)
    }

    /**
     * Handle feedback for the entire form
     * @param {"success"|"info"|"error"} type
     * @param {string} message
     * @returns {void}
     */
    const handleFormFeedback = (type, message) => {
        let feedback = form.querySelector(".form-feedback")
        if (!feedback) {
            feedback = document.createElement("div")
            feedback.classList.add("form-feedback", "alert", "alert-dismissible", "fade", "show")
            feedback.role = "alert"
            const span = document.createElement("span")
            feedback.append(span)
            const closeButton = document.createElement("button")
            closeButton.type = "button"
            closeButton.classList.add("btn-close")
            closeButton.ariaLabel = "Close"
            feedback.append(closeButton)
            form.prepend(feedback)
            Alert.getOrCreateInstance(feedback)
        }

        if (type === "success") {
            feedback.classList.remove("alert-info", "alert-danger")
            feedback.classList.add("alert-success")
        } else if (type === "info") {
            feedback.classList.remove("alert-success", "alert-danger")
            feedback.classList.add("alert-info")
        } else if (type === "error") {
            feedback.classList.remove("alert-success", "alert-info")
            feedback.classList.add("alert-danger")
        } else {
            console.error(`Unsupported feedback type: ${type}`)
            return
        }

        feedback.firstElementChild.textContent = message

        // Remove feedback on submit
        const onInvalidated = () => {
            if (!feedback) return
            Alert.getInstance(feedback).dispose()
            feedback.remove()
            feedback = null
            form.removeEventListener("submit", onInvalidated)
        }

        // Listen for events that invalidate the feedback
        form.addEventListener("submit", onInvalidated)
    }

    // Disable browser validation in favor of bootstrap
    form.noValidate = true
    form.classList.add("needs-validation")
    let pending = false

    // On form submit, build and submit the request
    const onSubmit = (e) => {
        e.preventDefault()

        // Check form validity
        if (!form.checkValidity()) {
            e.stopPropagation()
            form.classList.add("was-validated")
            return
        }

        form.classList.remove("was-validated")

        // Prevent double submission
        if (pending) {
            console.warn("Form already pending", form)
            return
        }

        pending = true
        toggleSubmit(false)

        fetch(form.action, {
            method: form.method,
            body: new FormData(form),
            mode: "same-origin",
            cache: "no-store",
            priority: "high",
        })
            .then(async (resp) => {
                const data = await resp.json()

                // Process form feedback if present
                if (data.detail) {
                    console.debug("Received form feedback", data.detail)

                    for (const {
                        type,
                        loc: [_, field],
                        msg,
                    } of data.detail) {
                        if (field) {
                            const input = form.querySelector(`[name=${field}]`)
                            // TODO: handle not found
                            if (input.type === "hidden") {
                                handleFormFeedback(type, msg)
                            } else {
                                handleElementFeedback(input, type, msg)
                            }
                        } else {
                            handleFormFeedback(type, msg)
                        }
                    }

                    form.classList.add("was-validated")
                }

                // If the request was successful, call the callback
                if (resp.ok && successCallback) successCallback(data)
            })
            .catch((error) => {
                console.error(error)
                handleFormFeedback("error", error.message)
            })
            .finally(() => {
                pending = false
                toggleSubmit(true)
            })
    }

    // Listen for events
    form.addEventListener("submit", onSubmit)
}
