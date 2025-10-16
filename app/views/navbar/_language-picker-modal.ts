import { Modal } from "bootstrap"
import { primaryLanguage } from "../lib/config"
import { staticCache } from "../lib/utils"

const languagePickerModal = document.querySelector("#languagePickerModal")
if (languagePickerModal) {
    const modalInstance = new Modal(languagePickerModal)
    const searchInput = languagePickerModal.querySelector("input")
    const languageButtons = languagePickerModal.querySelectorAll(
        ".language-list button",
    )

    // Move current language to top and mark as active (lazy)
    languagePickerModal.addEventListener(
        "show.bs.modal",
        () => {
            const languageList = languagePickerModal.querySelector(".language-list")
            for (const btn of languageButtons) {
                if (btn.dataset.lang === primaryLanguage) {
                    btn.setAttribute("class", "btn btn-primary fw-bold")
                    languageList.prepend(btn)
                    return
                }
            }
        },
        { once: true },
    )

    // Focus search input when modal is shown
    languagePickerModal.addEventListener("shown.bs.modal", () => {
        searchInput.focus()
    })

    // Reset modal when closed
    languagePickerModal.addEventListener("hidden.bs.modal", () => {
        // Reset search input
        searchInput.value = ""

        // Reset visibility of all options
        for (const btn of languageButtons) {
            btn.classList.remove("d-none")
        }
    })

    // Search functionality
    const nonAlphaRegex = /[^a-z\s]/g
    const getLowercasedTitles = staticCache(() =>
        Array.from(languageButtons).map((btn) => btn.title.toLowerCase()),
    )

    searchInput.addEventListener("input", () => {
        const searchTerm = searchInput.value
            .toLowerCase()
            .trim()
            .replace(nonAlphaRegex, "")
        const lowercasedTitles = getLowercasedTitles()

        languageButtons.forEach((btn, index) => {
            btn.classList.toggle(
                "d-none",
                !!searchTerm && !lowercasedTitles[index].includes(searchTerm),
            )
        })
    })

    // Language selection
    for (const btn of languageButtons) {
        btn.addEventListener("click", () => {
            const selectedLang = btn.dataset.lang
            if (selectedLang && selectedLang !== primaryLanguage) {
                console.info("Changing language to", selectedLang)
                // biome-ignore lint/suspicious/noDocumentCookie: acceptable
                document.cookie = `lang=${selectedLang}; path=/; max-age=31536000; samesite=lax`
                window.location.reload()
                btn.disabled = true
            } else {
                modalInstance.hide()
            }
        })
    }
}
