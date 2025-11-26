import { mount } from "../../lib/mount"
import { configureStandardForm } from "../../lib/standard-form"

mount("user-profile-body", () => {
    const modal = document.getElementById("profileSocialsModal")
    if (!modal) return

    const form = modal.querySelector("form")
    const container = form.querySelector(".socials-container") as HTMLElement
    const template = container.querySelector("template")
    const maxItems = Number.parseInt(container.dataset.maxItems, 10)
    const addBtn = form.querySelector("button.add-btn")

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
        const select = row.querySelector("select")
        const input = row.querySelector("input[name=value]")
        const label = row.querySelector(".custom-input-group label")
        const selected = select.selectedOptions[0]

        input.placeholder = selected.dataset.placeholder
        input.type = selected.dataset.hasTemplate ? "text" : "url"
        label.textContent = selected.dataset.label
    }

    /** Disable move buttons at boundaries */
    function updateMoveButtons(row: Element, index: number, total: number) {
        row.querySelector("button.move-up-btn").disabled = index === 0
        row.querySelector("button.move-down-btn").disabled = index === total - 1
    }

    /** Move a row up (swap with previous sibling) */
    function moveUp(row: Element) {
        container.insertBefore(row, row.previousElementSibling)
        updateState()
    }

    /** Move a row down (swap with next sibling) */
    function moveDown(row: Element) {
        container.insertBefore(row.nextElementSibling, row)
        updateState()
    }

    form.addEventListener("click", (e) => {
        const target = e.target as HTMLElement

        if (target.closest(".move-up-btn")) {
            moveUp(target.closest(".social-row"))
            return
        }

        if (target.closest(".move-down-btn")) {
            moveDown(target.closest(".social-row"))
            return
        }

        if (target.closest(".remove-btn")) {
            target.closest(".social-row").remove()
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
            updateRowState(target.closest(".social-row"))
        }
    })

    updateState()
})
