// On copy group input focus, select all text
const onCopyInputFocus = ({ target }) => {
    target.select()
}

// On copy group button click, copy input and change tooltip text
const onCopyButtonClick = async ({ target }) => {
    const copyButton = target.closest("button")
    const copyIcon = copyButton.querySelector("i")
    const copyGroup = copyButton.closest(".copy-group")
    const copyInput = copyGroup.querySelector(".form-control")

    // Visual feedback
    copyInput.select()

    try {
        // Write to clipboard
        const text = copyInput.value
        await navigator.clipboard.writeText(text)
        console.debug("Copied to clipboard")
    } catch (error) {
        console.error("Failed to write to clipboard", error)
        alert(error.message)
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
    const copyInput = copyGroup.querySelector(".form-control")
    copyInput.addEventListener("focus", onCopyInputFocus)
    const copyButton = copyGroup.querySelector(".bi-copy").parentElement
    copyButton.addEventListener("click", onCopyButtonClick)
}
