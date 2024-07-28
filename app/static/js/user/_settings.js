import i18next from "i18next"
import { configureStandardForm } from "../_standard-form.js"
import { isHrefCurrentPage } from "../_utils.js"

// Add active class to current nav-lik
const navLinks = document.querySelectorAll(".settings-nav .nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

const settingsBody = document.querySelector("body.settings-body")
if (settingsBody) {
    const settingsForm = settingsBody.querySelector("form.settings-form")
    const displayNameInput = settingsForm.elements.display_name
    const displayNameBlacklist = displayNameInput.dataset.blacklist
    const avatarForm = settingsBody.querySelector("form.avatar-form")
    const avatarTypeInput = avatarForm.elements.avatar_type
    const avatarFileInput = avatarForm.elements.avatar_file
    const uploadAvatarButton = avatarForm.querySelector("button.upload-avatar")
    const useGravatarButton = avatarForm.querySelector("button.use-gravatar")
    const removeAvatarButton = avatarForm.querySelector("button.remove-avatar")
    const avatars = document.querySelectorAll("img.avatar")

    const onSettingsFormSuccess = () => {
        location.reload()
    }

    const onSettingsClientValidation = () => {
        const result = new Array()

        const displayNameValue = displayNameInput.value
        if (displayNameBlacklist.split("").some((c) => displayNameValue.includes(c))) {
            const msg = i18next.t("validations.url_characters", {
                characters: displayNameBlacklist,
                interpolation: { escapeValue: false },
            })
            result.push({ type: "error", loc: ["", "display_name"], msg })
        }

        return result
    }

    const onAvatarFileChange = () => {
        avatarTypeInput.value = "custom"
        avatarForm.requestSubmit()
    }

    const onUploadAvatarClick = () => {
        avatarFileInput.click()
    }

    const onUseGravatarClick = () => {
        avatarTypeInput.value = "gravatar"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    const onRemoveAvatarClick = () => {
        avatarTypeInput.value = "default"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    // On successful avatar upload, update avatar images
    const onAvatarFormSuccess = (data) => {
        for (const avatar of avatars) avatar.src = data.avatar_url
    }

    configureStandardForm(settingsForm, onSettingsFormSuccess, onSettingsClientValidation)
    configureStandardForm(avatarForm, onAvatarFormSuccess)

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    useGravatarButton.addEventListener("click", onUseGravatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
}
