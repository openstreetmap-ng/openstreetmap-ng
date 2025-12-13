import { primaryLanguage } from "@lib/config"
import { getLocaleDisplayName, LOCALE_OPTIONS } from "@lib/locale"
import { Modal } from "bootstrap"

const NON_ALPHA_SPACE_RE = /[^a-z\s]/g

const languagePickerModal = document.getElementById("languagePickerModal")
if (languagePickerModal) {
    const modalInstance = new Modal(languagePickerModal)
    const searchInput = languagePickerModal.querySelector("input")!
    const languageList = languagePickerModal.querySelector(".language-list")!
    const languageButtons: HTMLButtonElement[] = []

    const initializeLanguages = () => {
        if (languageButtons.length) return
        console.debug("NavbarLanguage: Initializing picker")
        const fragment = document.createDocumentFragment()

        for (const locale of LOCALE_OPTIONS) {
            const [code, english, native, flag] = locale

            const listItem = document.createElement("li")
            const button = document.createElement("button")
            button.type = "button"
            button.dataset.search = [code, english, native]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
            button.title = getLocaleDisplayName(locale)

            if (flag) {
                const flagSpan = document.createElement("span")
                flagSpan.className = "flag"
                flagSpan.textContent = flag
                button.append(flagSpan)
            }

            const nativeName = document.createElement("span")
            nativeName.className = "name-native"
            nativeName.textContent = native ?? english
            button.append(nativeName)

            if (native) {
                const englishName = document.createElement("span")
                englishName.className = "name-english"
                englishName.textContent = english
                button.append(englishName)
            }

            button.addEventListener("click", () => {
                if (code !== primaryLanguage) {
                    console.info("NavbarLanguage: Change", code)
                    document.cookie = `lang=${code}; path=/; max-age=31536000; samesite=lax`
                    window.location.reload()
                    button.disabled = true
                } else {
                    modalInstance.hide()
                }
            })

            listItem.append(button)

            if (code === primaryLanguage) {
                // Move current language to top and mark as active (lazy)
                button.ariaCurrent = "true"
                fragment.prepend(listItem)
            } else {
                fragment.append(listItem)
            }

            languageButtons.push(button)
        }

        languageList.append(fragment)
    }

    languagePickerModal.addEventListener(
        "show.bs.modal",
        () => {
            initializeLanguages()
        },
        { once: true },
    )

    // Focus search input when modal is shown
    languagePickerModal.addEventListener("shown.bs.modal", () => {
        searchInput.focus()
    })

    // Reset modal when closed
    languagePickerModal.addEventListener("hidden.bs.modal", () => {
        searchInput.value = ""
        for (const btn of languageButtons) {
            btn.parentElement!.hidden = false
        }
    })

    // Search functionality
    searchInput.addEventListener("input", () => {
        const searchTerm = searchInput.value
            .toLowerCase()
            .trim()
            .replace(NON_ALPHA_SPACE_RE, " ")

        for (const btn of languageButtons) {
            btn.parentElement!.hidden =
                !!searchTerm && !btn.dataset.search!.includes(searchTerm)
        }
    })
}
