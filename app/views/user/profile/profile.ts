import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { formatMonthName, formatShortDate, formatWeekdayName } from "@lib/format"
import { mount } from "@lib/mount"
import { UserActivityChartSchema } from "@lib/proto/shared_pb"
import { configureStandardForm } from "@lib/standard-form"
import { Tooltip } from "bootstrap"
import i18next from "i18next"

mount("user-profile-body", (body) => {
    const avatarForm = body.querySelector("form.avatar-form")!
    const avatarDropdown = avatarForm.querySelector(".dropdown")

    // Check if editing features available
    if (avatarDropdown) {
        const avatars = document.querySelectorAll("img.avatar")
        const avatarTypeInput = avatarForm.querySelector("input[name=avatar_type]")!
        const avatarFileInput = avatarForm.querySelector("input[name=avatar_file]")!

        avatarFileInput.addEventListener("change", () => {
            avatarTypeInput.value = "custom"
            avatarForm.requestSubmit()
        })

        const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")!
        uploadAvatarButton.addEventListener("click", () => {
            avatarFileInput.click()
        })

        const useGravatarButton = avatarForm.querySelector("button.gravatar-btn")!
        useGravatarButton.addEventListener("click", () => {
            avatarTypeInput.value = "gravatar"
            avatarFileInput.value = ""
            avatarForm.requestSubmit()
        })

        const removeAvatarButton = avatarForm.querySelector("button.remove-btn")!
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

        const backgroundForm = body.querySelector("form.background-form")!
        const backgroundImage = backgroundForm.querySelector("img.background")!
        const backgroundFileInput = backgroundForm.querySelector(
            "input[name=background_file]",
        )!

        backgroundFileInput.addEventListener("change", () => {
            backgroundForm.requestSubmit()
        })

        const uploadBackgroundButton =
            backgroundForm.querySelector("button.upload-btn")!
        uploadBackgroundButton.addEventListener("click", () => {
            backgroundFileInput.click()
        })

        const removeBackgroundButton =
            backgroundForm.querySelector("button.remove-btn")!
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

    // Follow/unfollow form handler
    const followForm = body.querySelector("form.follow-form")
    if (followForm) {
        configureStandardForm(followForm, () => {
            // On follow/unfollow success, reload the page
            console.debug("onFollowFormSuccess")
            window.location.reload()
        })
    }

    // Socials modal handler
    const socialsModal = document.getElementById("profileSocialsModal")
    if (socialsModal) {
        const form = socialsModal.querySelector("form")!
        const container = form.querySelector<HTMLElement>(".socials-container")!
        const template = container.querySelector("template")!
        const maxItems = Number.parseInt(container.dataset.maxItems!, 10)
        const addBtn = form.querySelector("button.add-btn")!

        configureStandardForm(form, () => {
            window.location.reload()
        })

        /** Update add button state and all row states */
        function updateState() {
            const rows = container.querySelectorAll(".social-row")
            const count = rows.length

            addBtn.hidden = count >= maxItems

            rows.forEach((row, index) => {
                updateRowState(row)
                updateMoveButtons(row, index, count)
            })
        }

        /** Update input type, placeholder, and label based on selected service */
        function updateRowState(row: Element) {
            const select = row.querySelector("select")!
            const input = row.querySelector("input[name=value]")!
            const label = row.querySelector(".custom-input-group label")!
            const selected = select.selectedOptions[0]

            input.placeholder = selected.dataset.placeholder!
            input.type = selected.dataset.hasTemplate ? "text" : "url"
            label.textContent = selected.dataset.label!
        }

        /** Disable move buttons at boundaries */
        function updateMoveButtons(row: Element, index: number, total: number) {
            row.querySelector("button.move-up-btn")!.disabled = index === 0
            row.querySelector("button.move-down-btn")!.disabled = index === total - 1
        }

        /** Move a row up (swap with previous sibling) */
        function moveUp(row: Element) {
            container.insertBefore(row, row.previousElementSibling)
            updateState()
        }

        /** Move a row down (swap with next sibling) */
        function moveDown(row: Element) {
            container.insertBefore(row.nextElementSibling!, row)
            updateState()
        }

        form.addEventListener("click", (e) => {
            const target = e.target as HTMLElement

            if (target.closest(".move-up-btn")) {
                moveUp(target.closest(".social-row")!)
                return
            }

            if (target.closest(".move-down-btn")) {
                moveDown(target.closest(".social-row")!)
                return
            }

            if (target.closest(".remove-btn")) {
                target.closest(".social-row")!.remove()
                updateState()
                return
            }

            if (target.closest(".add-btn")) {
                container.appendChild(template.content.cloneNode(true))
                updateState()
            }
        })

        form.addEventListener("change", (e) => {
            const target = e.target as HTMLElement
            if (target.matches("select[name=service]")) {
                updateRowState(target.closest(".social-row")!)
            }
        })

        updateState()
    }

    const chartTable = body.querySelector("table.activity-chart[data-chart]")!
    const chartBody = document.createElement("tbody")
    const chart = fromBinary(
        UserActivityChartSchema,
        base64Decode(chartTable.dataset.chart!),
    )
    const chartLinkPrefix = `/user/${encodeURIComponent(chartTable.dataset.displayName!)}/history?date=`

    const dayMs = 86_400_000
    const startMs = Date.parse(`${chart.startDate}T00:00:00Z`)
    const totalWeeks = Math.ceil(chart.values.length / 7)

    const monthLabels = new Array(totalWeeks)

    const days = chart.values.map((value, index) => {
        const date = new Date(startMs + index * dayMs)
        const iso = date.toISOString().slice(0, 10)
        const week = Math.floor(index / 7)
        if (date.getUTCDate() === 1) {
            monthLabels[week] = formatMonthName(iso, "short")
        }
        return {
            iso,
            level: chart.levels[index],
            value,
            week,
            weekday: index % 7,
        }
    })

    const monthsRow = chartBody.insertRow()
    monthsRow.className = "months-row"
    monthsRow.ariaHidden = "true"

    monthsRow.insertCell().className = "month-cell"
    for (const label of monthLabels) {
        const cell = monthsRow.insertCell()
        cell.className = "month-cell"
        if (label) cell.textContent = label
    }

    const weekdayRows = Array.from({ length: 7 }, (_, weekday) => {
        const row = chartBody.insertRow()
        const labelCell = row.insertCell()
        labelCell.className = "week-cell"
        labelCell.ariaHidden = "true"
        if (weekday % 2 === 1) {
            labelCell.textContent = formatWeekdayName(
                new Date(startMs + weekday * dayMs).toISOString(),
                "short",
            )
        }
        return row
    })

    const activateTooltip = ({ target }: Event) => {
        const element = target as HTMLElement
        const [iso, valueStr] = element.ariaLabel!.split(": ")
        const value = Number.parseInt(valueStr, 10)
        const dateLabel = formatShortDate(iso)
        const title =
            value > 0
                ? i18next.t("user.activity.details.count", {
                      count: value,
                      date: dateLabel,
                  })
                : i18next.t("user.activity.details.no_activity", {
                      date: dateLabel,
                  })
        Tooltip.getOrCreateInstance(element, { customClass: "activity-tooltip", title })
        element.removeEventListener("pointerenter", activateTooltip)
        element.removeEventListener("focus", activateTooltip)
    }

    for (const day of days) {
        const cell = weekdayRows[day.weekday].insertCell()
        const element = document.createElement(day.value ? "a" : "div")
        if (day.value)
            (element as HTMLAnchorElement).href = `${chartLinkPrefix}${day.iso}`
        element.className = `activity activity-${day.level}`
        element.ariaLabel = `${day.iso}: ${day.value}`
        element.addEventListener("pointerenter", activateTooltip, { once: true })
        element.addEventListener("focus", activateTooltip, { once: true })
        cell.append(element)
    }

    chartTable.replaceChildren(chartBody)
})
