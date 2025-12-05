export const configureCopyGroups = (root: ParentNode) => {
    const elements = root.querySelectorAll(".copy-group")
    console.debug("Initializing", elements.length, "copy groups")

    for (const element of elements) {
        let button: HTMLElement | null = null
        let input: HTMLInputElement | null = null
        let timeout: ReturnType<typeof setTimeout> | null = null

        if (element.tagName === "BUTTON") {
            button = element as HTMLButtonElement
        } else {
            button = element.querySelector("i.bi-copy").parentElement
            input = element.querySelector("input.form-control")
        }

        // On copy group input focus, select all text
        input?.addEventListener("focus", () => input.select())

        // On copy group button click, copy input and change tooltip text
        button.addEventListener("click", async () => {
            console.debug("onCopyButtonClick")

            // Visual feedback
            input?.select()

            const text = input
                ? input.value
                : root.querySelector(button.dataset.copyTarget).textContent.trim()

            try {
                // Write to clipboard
                await navigator.clipboard.writeText(text)
                console.debug("Copied to clipboard")
            } catch (error) {
                console.warn("Failed to write to clipboard", error)
                alert(error.message)
                return
            }

            const icon = button.querySelector("i")
            icon.classList.remove("bi-copy")
            icon.classList.add("bi-check2")

            clearTimeout(timeout)
            timeout = setTimeout(() => {
                icon.classList.remove("bi-check2")
                icon.classList.add("bi-copy")
            }, 1500)
        })
    }
}

// Initialize on load
configureCopyGroups(document.body)
