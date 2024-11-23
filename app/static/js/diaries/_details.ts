import { configureStandardForm } from "../_standard-form"
import { configureStandardPagination } from "../_standard-pagination"

const body = document.querySelector("body.diary-details-body")
if (body) {
    const comments = document.getElementById("comments")
    configureStandardPagination(comments)

    const subscriptionForm = body.querySelector("form.subscription-form")
    if (subscriptionForm)
        configureStandardForm(subscriptionForm, () => {
            // On success callback, reload the page
            console.debug("onSubscriptionFormSuccess")
            window.location.reload()
        })

    const commentForm = body.querySelector("form.comment-form")
    if (commentForm)
        configureStandardForm(commentForm, () => {
            // On success callback, reload the page
            console.debug("onCommentFormSuccess")
            window.location.reload()
        })
}
