const messagesContainer = document.querySelector(".messages-container")
if (messagesContainer) {
    // Panel
    const toggleAllCheckbox = document.querySelector(".toggle-all-check")
    const numSelectedSpan = document.querySelector(".num-selected")
    const markReadButton = document.querySelector(".mark-read-btn")
    const markUnreadButton = document.querySelector(".mark-unread-btn")
    const deleteButton = document.querySelector(".delete-btn")

    // Table
    const toggleCheckboxes = document.querySelectorAll(".toggle-check")

    const messageIds = new Set()

    const refreshUi = () => {
        if (messageIds.size === 0) {
            toggleAllCheckbox.checked = false
            toggleAllCheckbox.indeterminate = false
            markReadButton.disabled = true
            markUnreadButton.disabled = true
            deleteButton.disabled = true
        } else {
            // messageIds.size > 0
            markReadButton.disabled = false
            markUnreadButton.disabled = false
            deleteButton.disabled = false

            if (messageIds.size < toggleCheckboxes.length) {
                toggleAllCheckbox.checked = false
                toggleAllCheckbox.indeterminate = true
            } else {
                toggleAllCheckbox.checked = true
                toggleAllCheckbox.indeterminate = false
            }
        }

        numSelectedSpan.textContent = messageIds.size
    }

    // Listen for panel events
    toggleAllCheckbox.addEventListener("change", () => {
        const checked = toggleAllCheckbox.checked
        for (const check of toggleCheckboxes) {
            check.checked = checked
            const id = check.dataset.messageId
            if (checked) messageIds.add(id)
            else messageIds.delete(id)
        }
        refreshUi()
    })

    // On form submit, add a hidden input with the message IDs
    // TODO: standard form
    for (const form of [
        markReadButton.closest("form"),
        markUnreadButton.closest("form"),
        deleteButton.closest("form"),
    ]) {
        form.addEventListener("submit", () => {
            const input = document.createElement("input")
            input.type = "hidden"
            input.name = "message_ids"
            input.value = JSON.stringify([...messageIds])
            form.append(input)
        })
    }

    // Listen for table events
    for (const check of toggleCheckboxes) {
        check.addEventListener("change", () => {
            const id = check.dataset.messageId
            const checked = check.checked
            if (checked) messageIds.add(id)
            else messageIds.delete(id)
            refreshUi()
        })
    }
}
