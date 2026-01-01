import { delay } from "@std/async/delay"
import { SECOND } from "@std/datetime/constants"

export const configureCopyGroups = (root: ParentNode) => {
    const elements = root.querySelectorAll(".copy-group")
    console.debug("CopyGroup: Initializing", elements.length)

    for (const element of elements) {
        let button: HTMLElement
        let input: HTMLInputElement | null
        let feedbackAbort: AbortController | undefined

        if (element.tagName === "BUTTON") {
            button = element as HTMLButtonElement
            input = null
        } else {
            button = element.querySelector("i.bi-copy")!.parentElement!
            input = element.querySelector("input.form-control")
        }

        // On copy group input focus, select all text
        input?.addEventListener("focus", input.select)

        // On copy group button click, copy input and change tooltip text
        button.addEventListener("click", async () => {
            console.debug("CopyGroup: Copying")

            // Visual feedback
            input?.select()

            const text = input
                ? input.value
                : root.querySelector(button.dataset.copyTarget!)!.textContent.trim()

            try {
                // Write to clipboard
                await navigator.clipboard.writeText(text)
                console.debug("CopyGroup: Copied")
            } catch (error) {
                console.warn("CopyGroup: Failed to copy", error)
                alert(error.message)
                return
            }

            const icon = button.querySelector("i")!
            icon.classList.remove("bi-copy")
            icon.classList.add("bi-check2")

            feedbackAbort?.abort()
            feedbackAbort = new AbortController()
            try {
                await delay(1.5 * SECOND, { signal: feedbackAbort.signal })
            } catch {
                return
            }
            icon.classList.remove("bi-check2")
            icon.classList.add("bi-copy")
        })
    }
}

// Initialize on load
configureCopyGroups(document.body)
