const abortControllers = new Map()

/**
 * Abort any pending request for the given source element, optionally returning a new AbortController
 * @param {HTMLElement} source Source element
 * @param {boolean} newController Whether to return a new AbortController
 * @returns {AbortController|null} AbortController if newController is true, null otherwise
 */
const abortRequest = (source, newController = false) => {
    const controller = abortControllers.get(source)
    if (controller) controller.abort()

    // When a new controller is requested, replace the old one and return it
    if (newController) {
        const controller = new AbortController()
        abortControllers.set(source, controller)
        return controller
    }

    // Otherwise, delete the controller and return null
    abortControllers.delete(source)
    return null
}

for (const container of document.querySelectorAll(".rich-text-container")) {
    // Discover all required elements
    const editBtn = container.querySelector(".edit-btn")
    const previewBtn = container.querySelector(".preview-btn")
    const sourceTextArea = container.querySelector(".rich-text-source")
    const previewDiv = container.querySelector(".rich-text-preview")

    // On edit button click, abort any requests and show the source textarea
    editBtn.addEventListener("click", () => {
        abortRequest(sourceTextArea)

        editBtn.disabled = true
        previewBtn.disabled = false
        sourceTextArea.classList.remove("d-none")
        previewDiv.classList.add("d-none")
        previewDiv.innerHTML = ""
    })

    // On preview button click, abort any requests and fetch the preview
    previewBtn.addEventListener("click", () => {
        const abortController = abortRequest(sourceTextArea, true)

        editBtn.disabled = false
        previewBtn.disabled = true
        sourceTextArea.classList.add("d-none")
        previewDiv.classList.remove("d-none")
        previewDiv.innerHTML = I18n.t("shared.richtext_field.loading")

        const formData = new FormData()
        formData.append("text", sourceTextArea.value)
        formData.append("text_format", "markdown")

        fetch("/api/web/rich_text/preview", {
            method: "POST",
            body: formData,
            signal: abortController.signal,
        })
            .then(async (resp) => {
                previewDiv.innerHTML = await resp.text()
            })
            .catch((error) => {
                if (error.name === "AbortError") return

                console.error(error)
                previewDiv.innerHTML = error.message
                // TODO: standard alert
            })
    })
}
