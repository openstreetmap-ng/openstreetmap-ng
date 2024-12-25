import i18next from "i18next"

const abortControllers: Map<Element, AbortController> = new Map()

/** Abort any pending request for the given source element, optionally returning a new AbortController */
const abortRequest = (source: Element, newController: boolean): AbortController | null => {
    const controller = abortControllers.get(source)
    controller?.abort()

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
    const sourceTextArea = container.querySelector("textarea.rich-text-source")
    const previewDiv = container.querySelector(".rich-text-preview")
    const helpDiv = container.querySelector(".rich-text-tips")

    /** On edit button click, abort any requests and show the source textarea */
    const onEditClick = () => {
        abortRequest(sourceTextArea, false)

        for (const button of editButtons) button.disabled = true
        for (const button of previewButtons) button.disabled = false
        for (const button of helpButtons) button.disabled = false

        sourceTextArea.classList.remove("d-none")
        previewDiv.classList.add("d-none")
        previewDiv.innerHTML = ""
        helpDiv.classList.add("d-none")
    }
    const editButtons = container.querySelectorAll("button.edit-btn")
    for (const button of editButtons) button.addEventListener("click", onEditClick)

    /** On preview button click, abort any requests and fetch the preview */
    const onPreviewClick = () => {
        const abortController = abortRequest(sourceTextArea, true)

        for (const button of editButtons) button.disabled = false
        for (const button of previewButtons) button.disabled = true
        for (const button of helpButtons) button.disabled = false

        sourceTextArea.classList.add("d-none")
        previewDiv.classList.remove("d-none")
        previewDiv.innerHTML = i18next.t("browse.start_rjs.loading")
        helpDiv.classList.add("d-none")

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
    const previewButtons = container.querySelectorAll("button.preview-btn")
    for (const button of previewButtons) button.addEventListener("click", onPreviewClick)

    /** On help button click, show the help content */
    const onHelpClick = () => {
        abortRequest(sourceTextArea, false)

        for (const button of editButtons) button.disabled = false
        for (const button of previewButtons) button.disabled = false
        for (const button of helpButtons) button.disabled = true

        sourceTextArea.classList.add("d-none")
        previewDiv.classList.add("d-none")
        previewDiv.innerHTML = ""
        helpDiv.classList.remove("d-none")
    }
    const helpButtons = container.querySelectorAll("button.help-btn")
    for (const button of helpButtons) button.addEventListener("click", onHelpClick)
}
