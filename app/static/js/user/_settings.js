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
    const avatarForm = settingsBody.querySelector("form.avatar-form")

    const avatars = document.querySelectorAll("img.avatar")
    const avatarTypeInput = avatarForm.elements.avatar_type
    const avatarFileInput = avatarForm.elements.avatar_file
    const uploadAvatarButton = avatarForm.querySelector("button.upload-avatar")
    const useGravatarButton = avatarForm.querySelector("button.use-gravatar")
    const removeAvatarButton = avatarForm.querySelector("button.remove-avatar")

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

    configureStandardForm(settingsForm)
    configureStandardForm(avatarForm, onAvatarFormSuccess)

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    useGravatarButton.addEventListener("click", onUseGravatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
}
