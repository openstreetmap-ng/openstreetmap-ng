/**
 * Tags direct edit functionality.
 * Allows users to edit tags inline when viewing the latest version of an element.
 */

/** Parse tags JSON from data attribute and convert to key=value format */
const tagsToText = (tags: Record<string, string>): string => {
    const entries = Object.entries(tags).sort(([a], [b]) => a.localeCompare(b))
    return entries.map(([key, value]) => `${key}=${value}`).join("\n")
}

/** Parse key=value text back into tags object */
const textToTags = (text: string): Record<string, string> => {
    const tags: Record<string, string> = {}
    for (const line of text.split("\n")) {
        const trimmed = line.trim()
        if (!trimmed) continue

        const eqIndex = trimmed.indexOf("=")
        if (eqIndex === -1) continue

        const key = trimmed.slice(0, eqIndex).trim()
        const value = trimmed.slice(eqIndex + 1).trim()
        if (key) tags[key] = value
    }
    return tags
}

/**
 * Configure the tags edit functionality for an element.
 * Called after the element content is loaded.
 */
export const configureTagsEdit = (container: HTMLElement) => {
    const tagsSection = container.querySelector(".tags-section")
    if (!tagsSection) return

    const editBtn = tagsSection.querySelector<HTMLButtonElement>(".edit-tags-btn")
    if (!editBtn) return // Not logged in or not latest version

    const tagsView = tagsSection.querySelector<HTMLElement>(".tags-view")!
    const editForm = tagsSection.querySelector<HTMLFormElement>(".tags-edit-form")!
    const textarea = editForm.querySelector<HTMLTextAreaElement>(".tags-textarea")!
    const discardBtn = editForm.querySelector<HTMLButtonElement>(".discard-tags-btn")!

    // Get tags from data attribute
    const tagsJson = tagsView.dataset.tags || "{}"
    const originalTags = JSON.parse(tagsJson) as Record<string, string>

    // Edit button: show form, hide tags
    editBtn.addEventListener("click", () => {
        console.debug("TagsEdit: Entering edit mode")
        textarea.value = tagsToText(originalTags)
        tagsView.classList.add("d-none")
        editBtn.classList.add("d-none")
        editForm.classList.remove("d-none")
        textarea.focus()
    })

    // Discard button: hide form, show tags
    discardBtn.addEventListener("click", () => {
        console.debug("TagsEdit: Discarding changes")
        editForm.classList.add("d-none")
        tagsView.classList.remove("d-none")
        editBtn.classList.remove("d-none")
    })

    // Form submit: currently frontend-only (API 0.7 not ready)
    // When backend is ready, this will be a standard form submission
    editForm.addEventListener("submit", (e) => {
        // For now, just log the parsed tags
        // Backend will handle the actual submission when API 0.7 is ready
        const newTags = textToTags(textarea.value)
        console.debug("TagsEdit: Would submit tags", newTags)

        // TODO: Remove this when API 0.7 endpoint is available
        e.preventDefault()
        alert("Tag editing will be available when API 0.7 is released.")
    })

    console.debug("TagsEdit: Configured for element")
}
