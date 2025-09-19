import { Tooltip } from "bootstrap"
import i18next from "i18next"
import { formatMonthName, formatShortDate, formatWeekdayName } from "../../lib/format"
import { mount } from "../../lib/mount"
import { configureStandardForm } from "../../lib/standard-form"

mount("user-profile-body", (body) => {
    const avatarForm = body.querySelector("form.avatar-form")
    const avatarDropdown = avatarForm.querySelector(".dropdown")

    // Check if editing features available
    if (avatarDropdown) {
        const avatars = document.querySelectorAll("img.avatar")
        const avatarTypeInput = avatarForm.elements.namedItem(
            "avatar_type",
        ) as HTMLInputElement
        const avatarFileInput = avatarForm.elements.namedItem(
            "avatar_file",
        ) as HTMLInputElement

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
            avatarTypeInput.value = ""
            avatarFileInput.value = ""
            avatarForm.requestSubmit()
        })

        configureStandardForm(avatarForm, ({ avatar_url }) => {
            // On successful avatar upload, update avatar images
            console.debug("onAvatarFormSuccess", avatar_url)
            for (const avatarImage of avatars) {
                avatarImage.src = avatar_url
            }
        })

        const backgroundForm = body.querySelector("form.background-form")
        const backgroundImage = backgroundForm.querySelector("img.background")
        const backgroundFileInput = backgroundForm.elements.namedItem(
            "background_file",
        ) as HTMLInputElement

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
                backgroundImage.src = background_url
            } else {
                backgroundImage.removeAttribute("src")
            }
        })

        const descriptionForm = body.querySelector("form.description-form")
        configureStandardForm(descriptionForm, () => {
            // On description update, reload the page
            console.debug("onDescriptionFormSuccess")
            window.location.reload()
        })
    }

    const activityChart = body.querySelector(".activity-chart")

    for (const cell of activityChart.querySelectorAll("td[data-date-iso]")) {
        cell.textContent = formatMonthName(cell.dataset.dateIso, "short")
    }

    for (const cell of activityChart.querySelectorAll("td[data-date-iso]")) {
        cell.textContent = formatWeekdayName(cell.dataset.dateIso, "short")
    }

    for (const element of activityChart.querySelectorAll<HTMLElement>(
        "[data-date-iso]",
    )) {
        const formattedDate = formatShortDate(element.dataset.dateIso)
        const value = Number(element.dataset.activityValue ?? "0")
        const tooltipText =
            value > 0
                ? i18next.t("user.activity.details.count", {
                      count: value,
                      date: formattedDate,
                  })
                : i18next.t("user.activity.details.no_activity", {
                      date: formattedDate,
                  })
        new Tooltip(element, { customClass: "activity-tooltip", title: tooltipText })
    }
})
