import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("report-show-body", () => {
    const setupVisibilityDropdowns = () => {
        for (const form of document.querySelectorAll("form.visibility-form")) {
            const select = form.querySelector("select[name=visible_to]")

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
    const commentForm = document.querySelector("form.comment-form")
    const closeForm = document.querySelector("form.close-form")
    const reopenForm = document.querySelector("form.reopen-form")

    if (commentForm) {
        const commentTextarea = commentForm.querySelector("textarea[name=body]")
        const commentBtn = commentForm.querySelector("button.comment-btn")
        const closeBtn = document.querySelector("button.close-btn")
        const commentCloseBtn = document.querySelector("button.comment-close-btn")
        const reopenBtn = document.querySelector("button.reopen-btn")
        const commentReopenBtn = document.querySelector("button.comment-reopen-btn")

        // Handle comment form submission
        configureStandardForm(commentForm, () => {
            // Reload page on success
            window.location.reload()
        })

        // Handle close/reopen form submission
        configureStandardForm(closeForm, () => {
            window.location.reload()
        })
        configureStandardForm(reopenForm, () => {
            window.location.reload()
        })

        // Toggle buttons based on comment input
        const updateButtons = () => {
            const hasComment = commentTextarea.value.trim().length > 0

            if (closeBtn && commentCloseBtn) {
                closeBtn.classList.toggle("d-none", hasComment)
                commentCloseBtn.classList.toggle("d-none", !hasComment)
            }

            if (reopenBtn && commentReopenBtn) {
                reopenBtn.classList.toggle("d-none", hasComment)
                commentReopenBtn.classList.toggle("d-none", !hasComment)
            }

            // Disable comment button if no text
            commentBtn.disabled = !hasComment
        }

        commentTextarea.addEventListener("input", updateButtons)

        // Initial state
        updateButtons()

        // Handle close button click
        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                closeForm.requestSubmit()
            })
        }
        if (commentCloseBtn) {
            commentCloseBtn.addEventListener("click", () => {
                const bodyInput = closeForm.querySelector("input[name=body]")
                bodyInput.value = commentTextarea.value
                closeForm.requestSubmit()
            })
        }

        // Handle reopen button click
        if (reopenBtn) {
            reopenBtn.addEventListener("click", () => {
                reopenForm.requestSubmit()
            })
        }
        if (commentReopenBtn) {
            commentReopenBtn.addEventListener("click", () => {
                const bodyInput = reopenForm.querySelector("input[name=body]")
                bodyInput.value = commentTextarea.value
                reopenForm.requestSubmit()
            })
        }
    }
})
