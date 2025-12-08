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
        console.debug("Initializing language picker")
        const fragment = document.createDocumentFragment()

        for (const locale of LOCALE_OPTIONS) {
            const displayName = locale.native ?? locale.english

            const listItem = document.createElement("li")
            const button = document.createElement("button")
            button.type = "button"
            button.dataset.search =
                `${locale.code} ${displayName}${locale.native ? ` ${locale.english}` : ""}`.toLowerCase()
            button.title = getLocaleDisplayName(locale)

            if (locale.flag) {
                const flag = document.createElement("span")
                flag.className = "flag"
                flag.textContent = locale.flag
                button.append(flag)
            }

            const nativeName = document.createElement("span")
            nativeName.className = "name-native"
            nativeName.textContent = displayName
            button.append(nativeName)

            if (locale.native) {
                const englishName = document.createElement("span")
                englishName.className = "name-english"
                englishName.textContent = locale.english
                button.append(englishName)
            }

            button.addEventListener("click", () => {
                if (locale.code !== primaryLanguage) {
                    console.info("Changing language to", locale.code)
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
