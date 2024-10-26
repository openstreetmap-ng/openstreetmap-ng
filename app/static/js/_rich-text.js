import i18next from "i18next"

const abortControllers = new Map()

/**
 * Abort any pending request for the given source element, optionally returning a new AbortController
 * @param {HTMLElement} source Source element
 * @param {boolean} newController Whether to return a new AbortController
 * @returns {AbortController|null} AbortController if newController is true, null otherwise
 */
const abortRequest = (source, newController) => {
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

const richTextContainers = document.querySelectorAll(".rich-text-container")
console.debug("Initializing", richTextContainers.length, "rich text containers")
for (const container of richTextContainers) {
    // Discover all required elements
    const editButton = container.querySelector(".edit-btn")
    const previewButton = container.querySelector(".preview-btn")
    const sourceTextArea = container.querySelector(".rich-text-source")
    const previewDiv = container.querySelector(".rich-text-preview")

    // On edit button click, abort any requests and show the source textarea
    const onEditButtonClick = () => {
        abortRequest(sourceTextArea, false)

        editButton.disabled = true
        previewButton.disabled = false
        sourceTextArea.classList.remove("d-none")
        previewDiv.classList.add("d-none")
        previewDiv.innerHTML = ""
    }

    // On preview button click, abort any requests and fetch the preview
    const onPreviewButtonClick = () => {
        const abortController = abortRequest(sourceTextArea, true)

        editButton.disabled = false
        previewButton.disabled = true
        sourceTextArea.classList.add("d-none")
        previewDiv.classList.remove("d-none")
        previewDiv.innerHTML = i18next.t("browse.start_rjs.loading")

        const formData = new FormData()
        formData.append("text", sourceTextArea.value)

        fetch("/api/web/rich-text", {
            method: "POST",
            body: formData,
            mode: "same-origin",
            cache: "no-store",
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                previewDiv.innerHTML = await resp.text()
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch rich text preview", error)
                previewDiv.innerHTML = error.message
                // TODO: standard alert
            })
    }

    // Listen for events
    editButton.addEventListener("click", onEditButtonClick)
    previewButton.addEventListener("click", onPreviewButtonClick)
}
