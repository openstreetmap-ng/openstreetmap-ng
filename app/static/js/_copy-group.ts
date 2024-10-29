const copyGroups = document.querySelectorAll(".copy-group")
console.debug("Initializing", copyGroups.length, "copy groups")
for (const copyGroup of copyGroups) {
    const copyInput = copyGroup.querySelector("input.form-control")
    const copyButton = copyGroup.querySelector("i.bi-copy").parentElement
    let timeout: ReturnType<typeof setTimeout> | null = null

    // On copy group input focus, select all text
    copyInput.addEventListener("focus", () => copyInput.select())

    // On copy group button click, copy input and change tooltip text
    copyButton.addEventListener("click", async () => {
        console.debug("onCopyGroupButtonClick")
        const copyIcon = copyButton.querySelector("i")

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

        if (timeout) clearTimeout(timeout)

        copyIcon.classList.remove("bi-copy")
        copyIcon.classList.add("bi-check2")

        timeout = setTimeout(() => {
            copyIcon.classList.remove("bi-check2")
            copyIcon.classList.add("bi-copy")
        }, 1500)
    })
}
