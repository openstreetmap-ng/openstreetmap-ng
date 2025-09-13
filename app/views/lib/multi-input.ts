import { t } from "i18next"

const multiInputContainers = document.querySelectorAll(".multi-input-container")
console.debug("Initializing", multiInputContainers.length, "multi-input components")

for (const container of multiInputContainers) {
    const form = container.closest("form")
    const input = container.querySelector("input[type=text]") as HTMLInputElement
    const tokensContainer = container.querySelector(".multi-input-tokens")

    const name = input.name
    input.removeAttribute("name")
    const placeholder = input.placeholder ?? ""
    const initiallyRequired = input.required
    const delimiter = ","

    const updateInputState = (): void => {
        const tokenCount = tokensContainer.querySelectorAll(".multi-input-token").length
        input.placeholder = tokenCount ? "" : placeholder
        input.required = initiallyRequired && !tokenCount
    }

    // Initialize with existing tokens
    const initializeTokens = (): void => {
        const values = input.value
            .trim()
            .split(delimiter)
            .map((v) => v.trim())
            .filter((v) => v)

        console.debug("Initializing", values.length, name, "tokens")

        for (const value of values) {
            createTokenElement(value)
        }
        input.value = ""
        updateInputState()
    }

    const createTokenElement = (token: string): void => {
        const tokenElement = document.createElement("span")
        tokenElement.className = "multi-input-token d-inline-flex align-items-center"

        const textSpan = document.createElement("span")
        textSpan.textContent = token
        textSpan.addEventListener("click", (e) => {
            e.stopPropagation()
            addTokenFromInput()
            input.value = token
            tokenElement.remove()
            updateInputState()
            input.focus()
            const len = input.value.length
            input.setSelectionRange(len, len)
        })

        const removeButton = document.createElement("button")
        removeButton.textContent = "×"
        removeButton.ariaLabel = t("action.remove")
        removeButton.addEventListener(
            "click",
            (e) => {
                e.stopPropagation()
                removeToken(tokenElement)
            },
            { once: true },
        )

        tokenElement.appendChild(textSpan)
        tokenElement.appendChild(removeButton)
        tokensContainer.appendChild(tokenElement)
    }

    const addToken = (value: string): void => {
        // Remove existing occurrence if it exists
        const existingTokens = tokensContainer.querySelectorAll(".multi-input-token")
        for (const tokenElement of existingTokens) {
            if (tokenElement.querySelector("span").textContent === value) {
                tokenElement.remove()
                break
            }
        }

        // Add token element
        createTokenElement(value)
        updateInputState()
    }

    const removeToken = (tokenElement: HTMLElement): void => {
        tokenElement.remove()
        updateInputState()
    }

    const editLastToken = (): void => {
        const tokenElements = tokensContainer.querySelectorAll(".multi-input-token")
        if (!tokenElements.length) return

        const tokenElement = tokenElements[tokenElements.length - 1]
        input.value = tokenElement.querySelector("span").textContent
        tokenElement.remove()
        updateInputState()
    }

    const addTokenFromInput = (): void => {
        const value = input.value.trim()
        if (value) {
            addToken(value)
            input.value = ""
        }
    }

    // Handle key events
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault()
            addTokenFromInput()
        } else if (
            e.key === "Backspace" &&
            !input.value &&
            tokensContainer.querySelectorAll(".multi-input-token").length
        ) {
            // Edit last token when backspace is pressed on empty input
            e.preventDefault()
            editLastToken()
        }
    })

    input.addEventListener("input", (e) => {
        const target = e.target as HTMLInputElement
        if (target.value.includes(delimiter)) {
            const allValues = target.value.split(delimiter)
            const values = allValues
                .slice(0, -1)
                .map((v) => v.trim())
                .filter((v) => v)

            for (const token of values) {
                addToken(token)
            }

            const remainingInput = allValues[allValues.length - 1].trim()
            target.value = remainingInput
        }
    })

    // Handle input blur
    input.addEventListener("blur", () => {
        if (document.activeElement !== input) {
            addTokenFromInput()
        }
    })

    // Handle form submission to auto-convert remaining input
    form?.addEventListener(
        "submit",
        () => {
            addTokenFromInput()

            // Remove existing hidden inputs
            for (const hiddenInput of container.querySelectorAll(
                "input[type=hidden]",
            )) {
                hiddenInput.remove()
            }

            // Add hidden input for each token
            const fragment = document.createDocumentFragment()
            const tokenElements = tokensContainer.querySelectorAll(".multi-input-token")
            console.debug("Adding", tokenElements.length, name, "tokens to form")
            for (const tokenElement of tokenElements) {
                const hiddenInput = document.createElement("input")
                hiddenInput.type = "hidden"
                hiddenInput.name = name
                hiddenInput.value = tokenElement.querySelector("span").textContent
                fragment.appendChild(hiddenInput)
            }
            input.parentElement.appendChild(fragment)
        },
        { capture: true },
    )

    initializeTokens()
}
