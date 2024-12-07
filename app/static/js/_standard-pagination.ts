import { resolveDatetime } from "./_datetime"

const paginationDistance = 2

export const configureStandardPagination = (container: HTMLElement): void => {
    const renderContainer = container.querySelector("ul.list-unstyled")
    const paginationContainers = container.querySelectorAll("ul.pagination")

    const dataset = paginationContainers[paginationContainers.length - 1].dataset
    const endpointPattern = dataset.action
    const totalPages = Number.parseInt(dataset.pages, 10)
    if (!totalPages) return
    console.debug("Initializing standard pagination", endpointPattern)
    let currentPage = totalPages
    let abortController: AbortController | null = null

    const getCurrentPageUrl = (): string => endpointPattern.replace("{page}", currentPage.toString())

    const setPendingState = (state: boolean): void => {
        renderContainer.style.opacity = state ? "0.5" : ""
    }

    const updateCollection = (): void => {
        console.debug("configureStandardPagination", "updateCollection", currentPage)
        abortController?.abort()
        abortController = new AbortController()
        setPendingState(true)
        fetch(getCurrentPageUrl(), {
            method: "GET",
            mode: "same-origin",
            cache: "no-store",
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (resp.ok) console.debug("Form submitted successfully")
                renderContainer.innerHTML = await resp.text()
                resolveDatetime(renderContainer)
            })
            .catch((error: Error) => {
                if (error.name === "AbortError") return
                console.error("Failed to submit standard form", error)
                renderContainer.textContent = error.message
            })
            .finally(() => {
                setPendingState(false)
            })
    }

    const updatePagination = (): void => {
        if (totalPages <= 1) {
            for (const paginationContainer of paginationContainers) {
                paginationContainer.classList.add("d-none")
            }
            return
        }
        console.debug("configureStandardPagination", "updatePagination", currentPage)

        for (const paginationContainer of paginationContainers) {
            paginationContainer.classList.remove("d-none")
            const paginationFragment = document.createDocumentFragment()

            for (let i = 1; i <= totalPages; i++) {
                const distance = Math.abs(i - currentPage)
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
                button.classList.add("page-link")
                button.textContent = i.toString()
                li.appendChild(button)

                if (i === currentPage) {
                    li.classList.add("active")
                    li.ariaCurrent = "page"
                } else {
                    button.addEventListener("click", () => {
                        currentPage = i
                        updateCollection()
                        updatePagination()
                    })
                }

                paginationFragment.appendChild(li)
            }

            paginationContainer.innerHTML = ""
            paginationContainer.appendChild(paginationFragment)
        }
    }

    // Initial update
    updateCollection()
    updatePagination()
}
