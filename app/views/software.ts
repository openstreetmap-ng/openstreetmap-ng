import { mount } from "@lib/mount"

mount("software-body", (body) => {
    const categoryFilter = body.querySelector("select#software-category-filter")!
    const platformFilter = body.querySelector("select#software-platform-filter")!
    const licenseFilter = body.querySelector("select#software-license-filter")!
    const cards = body.querySelectorAll(".software-card")
    const categories = body.querySelectorAll("section.software-category")
    const noResults = body.querySelector(".software-no-results")!
    const countEl = body.querySelector(".software-count")!

    const applyFilters = () => {
        const cat = categoryFilter.value
        const plat = platformFilter.value
        const lic = licenseFilter.value

        let visibleCount = 0

        for (const card of cards) {
            const el = card as HTMLElement
            const cardCat = el.dataset.category!
            const cardPlatforms = el.dataset.platforms!.split(",")
            const cardLicense = el.dataset.license!

            const matchCat = cat === "all" || cardCat === cat
            const matchPlat =
                plat === "all" || cardPlatforms.includes(plat)
            const matchLic = lic === "all" || cardLicense === lic

            const visible = matchCat && matchPlat && matchLic
            el.classList.toggle("d-none", !visible)
            if (visible) visibleCount++
        }

        // Hide empty category sections
        for (const section of categories) {
            const el = section as HTMLElement
            const hasVisible =
                el.querySelector(".software-card:not(.d-none)") !== null
            el.classList.toggle("d-none", !hasVisible)
        }

        noResults.classList.toggle("d-none", visibleCount > 0)
        countEl.textContent =
            `Showing ${visibleCount} of ${cards.length} entries`
    }

    categoryFilter.addEventListener("change", applyFilters)
    platformFilter.addEventListener("change", applyFilters)
    licenseFilter.addEventListener("change", applyFilters)

    applyFilters()
})
