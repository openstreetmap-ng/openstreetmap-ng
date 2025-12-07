import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("report-show-body", () => {
    const setupVisibilityDropdowns = () => {
        for (const form of document.querySelectorAll("form.visibility-form")) {
            const select = form.querySelector("select[name=visible_to]")!

            // Store the current value for rollback on error
            let currentValue = select.value

            select.addEventListener("change", () => {
                select.classList.add("disabled")
                form.requestSubmit()
            })

            configureStandardForm(
                form,
                () => {
                    currentValue = select.value
                    select.classList.remove("disabled")
                    console.debug("Visibility changed successfully to", currentValue)
                },
                {
                    errorCallback: () => {
                        select.value = currentValue
                        select.classList.remove("disabled")
                        console.error("Visibility change failed, rolling back")
                    },
                },
            )
        }
    }

    configureStandardPagination(
        document.querySelector("div.report-comments-pagination"),
        {
            loadCallback: setupVisibilityDropdowns,
        },
    )

    // Configure forms
    const commentForm = document.querySelector("form.comment-form")!
    const closeForm = document.querySelector("form.close-form")!
    const reopenForm = document.querySelector("form.reopen-form")!

    const commentTextarea = commentForm.querySelector("textarea[name=body]")!
    const commentButton = commentForm.querySelector("button.comment-btn")!
    const closeButton = document.querySelector("button.close-btn")
    const commentCloseButton = document.querySelector("button.comment-close-btn")
    const reopenButton = document.querySelector("button.reopen-btn")
    const commentReopenButton = document.querySelector("button.comment-reopen-btn")

    configureStandardForm(commentForm, () => {
        window.location.reload()
    })
    configureStandardForm(closeForm, () => {
        window.location.reload()
    })
    configureStandardForm(reopenForm, () => {
        window.location.reload()
    })

    // Toggle buttons based on comment input
    const updateButtons = () => {
        const hasComment = commentTextarea.value.trim().length > 0

        if (closeButton && commentCloseButton) {
            closeButton.classList.toggle("d-none", hasComment)
            commentCloseButton.classList.toggle("d-none", !hasComment)
        }

        if (reopenButton && commentReopenButton) {
            reopenButton.classList.toggle("d-none", hasComment)
            commentReopenButton.classList.toggle("d-none", !hasComment)
        }

        // Disable comment button if no text
        commentButton.disabled = !hasComment
    }

    commentTextarea.addEventListener("input", updateButtons)

    // Initial state
    updateButtons()

    // Handle close button click
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            closeForm.requestSubmit()
        })
    }
    if (commentCloseButton) {
        commentCloseButton.addEventListener("click", () => {
            const bodyInput = closeForm.querySelector("input[name=body]")!
            bodyInput.value = commentTextarea.value
            closeForm.requestSubmit()
        })
    }

    // Handle reopen button click
    if (reopenButton) {
        reopenButton.addEventListener("click", () => {
            reopenForm.requestSubmit()
        })
    }
    if (commentReopenButton) {
        commentReopenButton.addEventListener("click", () => {
            const bodyInput = reopenForm.querySelector("input[name=body]")!
            bodyInput.value = commentTextarea.value
            reopenForm.requestSubmit()
        })
    }
})
