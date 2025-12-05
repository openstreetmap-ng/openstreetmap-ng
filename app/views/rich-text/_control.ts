import { effect, signal } from "@preact/signals-core"
import i18next from "i18next"

const richTextContainers = document.querySelectorAll(".rich-text-container")
console.debug("Initializing", richTextContainers.length, "rich text containers")
for (const container of richTextContainers) {
    const sourceTextArea = container.querySelector("textarea.rich-text-source")
    const previewDiv = container.querySelector(".rich-text-preview")
    const helpDiv = container.querySelector(".rich-text-tips")

    const state = signal<"edit" | "preview" | "help" | undefined>()

    effect(() => {
        const stateValue = state.value
        if (!stateValue) return

        const isEdit = stateValue === "edit"
        const isPreview = stateValue === "preview"
        const isHelp = stateValue === "help"

        for (const btn of editButtons) btn.disabled = isEdit
        for (const btn of previewButtons) btn.disabled = isPreview
        for (const btn of helpButtons) btn.disabled = isHelp

        sourceTextArea.classList.toggle("d-none", !isEdit)
        previewDiv.classList.toggle("d-none", !isPreview)
        previewDiv.innerHTML = isPreview ? i18next.t("browse.start_rjs.loading") : ""
        helpDiv.classList.toggle("d-none", !isHelp)

        if (isPreview) {
            const abortController = new AbortController()

            const formData = new FormData()
            formData.append("text", sourceTextArea.value)

            const fetchPreview = async () => {
                try {
                    const resp = await fetch("/api/web/rich-text", {
                        method: "POST",
                        body: formData,
                        signal: abortController.signal,
                        priority: "high",
                    })
                    previewDiv.innerHTML = await resp.text()
                } catch (error) {
                    if (error.name === "AbortError") return
                    console.error("Failed to fetch rich text preview", error)
                    previewDiv.innerHTML = error.message
                    // TODO: standard alert
                }
            }
            fetchPreview()

            return () => abortController.abort()
        }
    })

    const editButtons = container.querySelectorAll("button.edit-btn")
    for (const btn of editButtons)
        btn.addEventListener("click", () => {
            state.value = "edit"
        })

    const previewButtons = container.querySelectorAll("button.preview-btn")
    for (const btn of previewButtons)
        btn.addEventListener("click", () => {
            state.value = "preview"
        })

    const helpButtons = container.querySelectorAll("button.help-btn")
    for (const btn of helpButtons)
        btn.addEventListener("click", () => {
            state.value = "help"
        })
}
