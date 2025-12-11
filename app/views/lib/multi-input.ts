import { t } from "i18next"

const multiInputContainers = document.querySelectorAll(".multi-input-container")
console.debug("MultiInput: Initializing", multiInputContainers.length)

for (const container of multiInputContainers) {
    const form = container.closest("form")
    const input = container.querySelector("input[type=text]")!
    const tokensContainer = container.querySelector(".multi-input-tokens")!

    const name = input.name
    input.removeAttribute("name")
    const placeholder = input.placeholder ?? ""
    const initiallyRequired = input.required
    const delimiter = ","

    const tokens = new Map<string, HTMLElement>()

    const updateInputState = () => {
        const count = tokens.size
        input.placeholder = count ? "" : placeholder
        input.required = initiallyRequired && !count
    }

    const createTokenElement = (value: string) => {
        const tokenElement = document.createElement("span")
        tokenElement.className = "multi-input-token d-inline-flex align-items-center"
        tokenElement.addEventListener("click", (e) => {
            e.stopPropagation()
            addTokenFromInput()
            input.value = value

            // tokenElement may have been removed by addTokenFromInput
            tokens.get(value)!.remove()
            tokens.delete(value)
            updateInputState()

            input.focus()
            const len = input.value.length
            input.setSelectionRange(len, len)
        })

        const textSpan = document.createElement("span")
        textSpan.textContent = value

        const removeButton = document.createElement("button")
        removeButton.type = "button"
        removeButton.textContent = "×"
        removeButton.ariaLabel = t("action.remove")
        removeButton.addEventListener(
            "click",
            (e) => {
                e.stopPropagation()
                tokenElement.remove()
                tokens.delete(value)
                updateInputState()
            },
            { once: true },
        )

        tokenElement.appendChild(textSpan)
        tokenElement.appendChild(removeButton)

        tokens.get(value)?.remove()
        tokens.set(value, tokenElement)
        return tokenElement
    }

    const addToken = (value: string) => {
        value = value.trim()
        if (!value) return

        const tokenElement = createTokenElement(value)
        tokensContainer.appendChild(tokenElement)
        updateInputState()
    }

    const editLastToken = () => {
        const tokenElement = tokensContainer.lastElementChild
        if (!tokenElement) return

        const tokenValue = tokenElement.querySelector("span")!.textContent
        input.value = tokenValue
        tokenElement.remove()
        tokens.delete(tokenValue)
        updateInputState()
    }

    const addTokenFromInput = () => {
        const value = input.value.trim()
        if (!value) return
        addToken(value)
        input.value = ""
    }

    // Keyboard handling
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault()
            addTokenFromInput()
        } else if (e.key === "Backspace" && !input.value && tokens.size) {
            e.preventDefault()
            editLastToken()
        }
    })

    // Tokenize on comma as you type
    input.addEventListener("input", () => {
        if (!input.value.includes(delimiter)) return

        const parts = input.value.split(delimiter)
        for (const p of parts.slice(0, -1)) addToken(p)
        input.value = parts.at(-1)!.trim()
    })

    // Commit remaining value on blur
    input.addEventListener("blur", addTokenFromInput)

    // On submit, convert tokens to hidden inputs
    form?.addEventListener(
        "submit",
        () => {
            addTokenFromInput()

            // Remove existing hidden inputs
            for (const hiddenInput of container.querySelectorAll("input[type=hidden]"))
                hiddenInput.remove()

            // Add hidden input for each token
            const fragment = document.createDocumentFragment()
            console.debug("MultiInput: Submitting", tokens.size, name, "tokens")
            for (const tokenElement of tokensContainer.children) {
                const hiddenInput = document.createElement("input")
                hiddenInput.type = "hidden"
                hiddenInput.name = name
                hiddenInput.value = tokenElement.querySelector("span")!.textContent
                fragment.appendChild(hiddenInput)
            }
            input.parentElement!.appendChild(fragment)
        },
        { capture: true },
    )

    // Initialize with existing comma-separated value
    const initializeTokens = () => {
        const values = input.value
            .trim()
            .split(delimiter)
            .map((v) => v.trim())
            .filter(Boolean)
        if (values.length) {
            const frag = document.createDocumentFragment()
            for (const v of values) frag.appendChild(createTokenElement(v))
            tokensContainer.appendChild(frag)
        }
        input.value = ""
        updateInputState()
    }

    initializeTokens()
}
