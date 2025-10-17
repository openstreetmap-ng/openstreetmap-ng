import { Modal } from "bootstrap"
import { primaryLanguage } from "../lib/config"
import { getLocaleOptions } from "../lib/locale"

const languagePickerModal = document.querySelector("#languagePickerModal")
if (languagePickerModal) {
    const modalInstance = new Modal(languagePickerModal)
    const searchInput = languagePickerModal.querySelector("input")
    const languageList = languagePickerModal.querySelector(".language-list")
    const languageButtons: HTMLButtonElement[] = []

    const initializeLanguages = () => {
        if (languageButtons.length) return
        console.debug("Initializing language picker")
        const fragment = document.createDocumentFragment()

        for (const locale of getLocaleOptions()) {
            const hasEnglishName = locale.nativeName !== locale.englishName

            const listItem = document.createElement("li")
            const button = document.createElement("button")
            button.type = "button"
            button.dataset.search =
                `${locale.code} ${locale.nativeName}${hasEnglishName ? ` ${locale.englishName}` : ""}`.toLowerCase()
            button.title = locale.displayName

            if (locale.flag) {
                const flag = document.createElement("span")
                flag.className = "flag"
                flag.textContent = locale.flag
                button.append(flag)
            }

            const nativeName = document.createElement("span")
            nativeName.className = "name-native"
            nativeName.textContent = locale.nativeName
            button.append(nativeName)

            if (hasEnglishName) {
                const englishName = document.createElement("span")
                englishName.className = "name-english"
                englishName.textContent = locale.englishName
                button.append(englishName)
            }

            button.addEventListener("click", () => {
                if (locale.code !== primaryLanguage) {
                    console.info("Changing language to", locale.code)
                    // biome-ignore lint/suspicious/noDocumentCookie: acceptable
                    document.cookie = `lang=${locale.code}; path=/; max-age=31536000; samesite=lax`
                    window.location.reload()
                    button.disabled = true
                } else {
                    modalInstance.hide()
                }
            })

            listItem.append(button)

            if (locale.code === primaryLanguage) {
                // Move current language to top and mark as active (lazy)
                button.setAttribute("aria-current", "true")
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
            btn.parentElement.hidden = false
        }
    })

    // Search functionality
    searchInput.addEventListener("input", () => {
        const searchTerm = searchInput.value
            .toLowerCase()
            .trim()
            .replace(/[^a-z\s]/g, " ")

        for (const btn of languageButtons) {
            btn.parentElement.hidden =
                !!searchTerm && !btn.dataset.search.includes(searchTerm)
        }
    })
}
