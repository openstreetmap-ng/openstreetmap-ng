interface HTMLElementWithTimeout extends HTMLElement {
    timeout: NodeJS.Timeout | null
}

// On copy group input focus, select all text
const onCopyInputFocus = ({ target }: FocusEvent) => {
    if (!target) return
    ;(target as HTMLInputElement).select()
}

// On copy group button click, copy input and change tooltip text
const onCopyButtonClick = async ({ target }: Event) => {
    if (!target) return
    const copyButton = (target as HTMLElement).closest("button")
    const copyIcon = copyButton.querySelector("i") as HTMLElementWithTimeout
    const copyGroup = copyButton.closest(".copy-group")
    const copyInput: HTMLInputElement = copyGroup.querySelector("input.form-control")

    // Visual feedback
    copyInput.select()

    try {
        // Write to clipboard
        const text = copyInput.value
        await navigator.clipboard.writeText(text)
        console.debug("Copied to clipboard")
    } catch (error) {
        console.warn("Failed to write to clipboard", error)
        if (error instanceof Error) alert(error.message)
        return
    }

    if (copyIcon.timeout) clearTimeout(copyIcon.timeout)

    copyIcon.classList.remove("bi-copy")
    copyIcon.classList.add("bi-check2")

    copyIcon.timeout = setTimeout(() => {
        copyIcon.classList.remove("bi-check2")
        copyIcon.classList.add("bi-copy")
    }, 1500)
}

const copyGroups = document.querySelectorAll(".copy-group")
console.debug("Initializing", copyGroups.length, "copy groups")
for (const copyGroup of copyGroups) {
    const copyInput: HTMLInputElement = copyGroup.querySelector("input.form-control")
    copyInput.addEventListener("focus", onCopyInputFocus)
    const copyButton = copyGroup.querySelector("i.bi-copy").parentElement as HTMLButtonElement
    copyButton.addEventListener("click", onCopyButtonClick)
}
