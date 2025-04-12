import i18next from "i18next"
import { resolveDatetimeLazy } from "./datetime"
import { effect, signal } from "@preact/signals-core"

const paginationDistance = 2

export const configureStandardPagination = (container?: HTMLElement): void => {
    if (!container) return
    const renderContainer = container.querySelector("ul.list-unstyled")
    const paginationContainers = container.querySelectorAll("ul.pagination")

    const dataset = paginationContainers[paginationContainers.length - 1].dataset
    const endpointPattern = dataset.action
    const totalPages = Number.parseInt(dataset.pages, 10)
    if (!totalPages) return

    console.debug("Initializing standard pagination", endpointPattern)
    const currentPage = signal(totalPages)
    let firstLoad = true

    const setPendingState = (state: boolean): void => {
        renderContainer.style.opacity = !firstLoad && state ? "0.5" : ""

        // Only show spinner during initial load
        if (firstLoad && state) {
            firstLoad = false
            const spinner = document.createElement("div")
            spinner.className = "text-center pagination-spinner"

            const spinnerElement = document.createElement("div")
            spinnerElement.className = "spinner-border text-body-secondary"
            spinnerElement.setAttribute("role", "status")

            const srText = document.createElement("span")
            srText.className = "visually-hidden"
            srText.textContent = i18next.t("browse.start_rjs.loading")

            spinnerElement.appendChild(srText)
            spinner.appendChild(spinnerElement)
            renderContainer.innerHTML = ""
            renderContainer.appendChild(spinner)
        }
    }

    // Update collection
    effect(() => {
        console.debug("configureStandardPagination", "updateCollection", currentPage)

        const abortController = new AbortController()

        setPendingState(true)
        fetch(endpointPattern.replace("{page}", currentPage.toString()), {
            method: "GET",
            mode: "same-origin",
            cache: "no-store",
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (resp.ok) console.debug("Form submitted successfully")
                renderContainer.innerHTML = await resp.text()
                resolveDatetimeLazy(renderContainer)
            })
            .catch((error: Error) => {
                if (error.name === "AbortError") return
                console.error("Failed to submit standard form", error)
                renderContainer.textContent = error.message
            })
            .finally(() => {
                setPendingState(false)
            })

        return () => abortController.abort()
    })

    // Update pagination
    effect(() => {
        if (totalPages <= 1) {
            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.add("d-none")
            }
            return
        }
        console.debug("configureStandardPagination", "updatePagination", currentPage)
        const currentPageValue = currentPage.value

        for (const paginationContainer of paginationContainers) {
            paginationContainer.classList.remove("d-none")
            const paginationFragment = document.createDocumentFragment()

            for (let i = 1; i <= totalPages; i++) {
                const distance = Math.abs(i - currentPageValue)
                if (distance > paginationDistance && i !== 1 && i !== totalPages) {
                    if (i === 2 || i === totalPages - 1) {
                        const li = document.createElement("li")
                        li.classList.add("page-item", "disabled")
                        li.ariaDisabled = "true"
                        li.innerHTML = `<span class="page-link">...</span>`
                        paginationFragment.appendChild(li)
                    }
                    continue
                }

                const li = document.createElement("li")
                li.classList.add("page-item")

                const button = document.createElement("button")
                button.type = "button"
                button.classList.add("page-link")
                button.textContent = i.toString()
                li.appendChild(button)

                if (i === currentPageValue) {
                    li.classList.add("active")
                    li.ariaCurrent = "page"
                } else {
                    button.addEventListener("click", () => {
                        currentPage.value = i
                    })
                }

                paginationFragment.appendChild(li)
            }

            paginationContainer.innerHTML = ""
            paginationContainer.appendChild(paginationFragment)
        }
    })
}
