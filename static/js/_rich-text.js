const abortControllers = new Map()

// Abort requests for the given source and optionally return a new AbortController
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

for (const group of document.querySelectorAll(".rich-text-btn-group")) {
    // Discover all required elements
    const editBtn = group.querySelector(".rich-text-edit-btn")
    const previewBtn = group.querySelector(".rich-text-preview-btn")
    const sourceTextArea = document.querySelector(group.dataset.richTextSource)
    const previewDiv = document.querySelector(group.dataset.richTextPreview)

    // On edit button click, abort any requests and show the source textarea
    editBtn.on("click", () => {
        abortRequest(sourceTextArea)

        editBtn.disabled = true
        previewBtn.disabled = false
        sourceTextArea.classList.remove("d-none")
        previewDiv.classList.add("d-none")
        previewDiv.innerHTML = ""
    })

    // On preview button click, abort any requests and fetch the preview
    previewBtn.on("click", () => {
        const abortController = abortRequest(source, true)

        editBtn.disabled = false
        previewBtn.disabled = true
        previewDiv.innerHTML = I18n.t("shared.richtext_field.loading")
        sourceTextArea.classList.add("d-none")
        previewDiv.classList.remove("d-none")

        const formData = new FormData()
        formData.append("text", sourceTextArea.value)
        formData.append("text_format", "markdown")

        fetch("/api/web/rich_text/preview", {
            method: "POST",
            body: formData,
            signal: abortController.signal,
        })
            .then((resp) => resp.text())
            .then((text) => {
                previewDiv.innerHTML = text
            })
            .catch((error) => {
                if (error.name === "AbortError") return

                console.error(error)
                previewDiv.innerHTML = error.message
            })
    })
}
