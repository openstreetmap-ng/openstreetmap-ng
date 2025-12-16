import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("follows-body", (body) => {
    const paginationContainer = body.querySelector(".follows-pagination")

    const setupFollowForms = (container: HTMLElement, page: number) => {
        for (const form of container.querySelectorAll("form.follow-form")) {
            configureStandardForm(form, () => {
                console.debug("Follows: Toggled", form.action)
                disposePagination()
                disposePagination = configureStandardPagination(paginationContainer, {
                    initialPage: page,
                    loadCallback: setupFollowForms,
                })
            })
        }
    }

    let disposePagination = configureStandardPagination(paginationContainer, {
        loadCallback: setupFollowForms,
    })
})
