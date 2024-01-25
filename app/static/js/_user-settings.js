import { configureStandardForm } from "./_standard-form.js"

const userSettingsForm = document.querySelector(".user-settings-form")
if (userSettingsForm) {
    configureStandardForm(userSettingsForm)

    const avatarFileRadio = userSettingsForm.querySelector(".avatar-file-radio")
    const avatarFileInput = userSettingsForm.querySelector(".avatar-file-input")

    // On file input, select the file radio
    const onAvatarFileInputChange = () => {
        avatarFileRadio.checked = true
    }

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileInputChange)
}
