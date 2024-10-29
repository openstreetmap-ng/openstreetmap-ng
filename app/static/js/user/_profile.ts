import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.user-profile-body")
if (body) {
    const avatarForm = body.querySelector("form.avatar-form")
    const avatarDropdown = avatarForm.querySelector(".dropdown")

    // Check if editing features available
    if (avatarDropdown) {
        const avatars = document.querySelectorAll("img.avatar")
        const avatarTypeInput = avatarForm.elements.namedItem("avatar_type") as HTMLInputElement
        const avatarFileInput = avatarForm.elements.namedItem("avatar_file") as HTMLInputElement

        avatarFileInput.addEventListener("change", () => {
            avatarTypeInput.value = "custom"
            avatarForm.requestSubmit()
        })

        const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")
        uploadAvatarButton.addEventListener("click", () => {
            avatarFileInput.click()
        })

        const useGravatarButton = avatarForm.querySelector("button.gravatar-btn")
        useGravatarButton.addEventListener("click", () => {
            avatarTypeInput.value = "gravatar"
            avatarFileInput.value = ""
            avatarForm.requestSubmit()
        })

        const removeAvatarButton = avatarForm.querySelector("button.remove-btn")
        removeAvatarButton.addEventListener("click", () => {
            avatarTypeInput.value = "default"
            avatarFileInput.value = ""
            avatarForm.requestSubmit()
        })

        configureStandardForm(avatarForm, ({ avatar_url }) => {
            // On successful avatar upload, update avatar images
            console.debug("onAvatarFormSuccess", avatar_url)
            for (const avatar of avatars) {
                avatar.src = avatar_url
            }
        })

        const backgroundForm = body.querySelector("form.background-form")
        const background = backgroundForm.querySelector("img.background")
        const backgroundFileInput = backgroundForm.elements.namedItem("background_file") as HTMLInputElement

        backgroundFileInput.addEventListener("change", () => {
            backgroundForm.requestSubmit()
        })

        const uploadBackgroundButton = backgroundForm.querySelector("button.upload-btn")
        uploadBackgroundButton.addEventListener("click", () => {
            backgroundFileInput.click()
        })

        const removeBackgroundButton = backgroundForm.querySelector("button.remove-btn")
        removeBackgroundButton.addEventListener("click", () => {
            backgroundFileInput.value = ""
            backgroundForm.requestSubmit()
        })

        configureStandardForm(backgroundForm, ({ background_url }) => {
            // On successful background upload, update background images
            console.debug("onBackgroundFormSuccess", background_url)
            if (background_url) {
                background.src = background_url
            } else {
                background.removeAttribute("src")
            }
        })

        const descriptionForm = body.querySelector("form.description-form")
        configureStandardForm(descriptionForm, () => {
            // On description update, reload the page
            console.debug("onDescriptionFormSuccess")
            window.location.reload()
        })
    }
}
