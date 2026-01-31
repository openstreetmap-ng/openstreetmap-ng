import { configureBootstrapPopovers, configureBootstrapTooltips } from "@lib/bootstrap"
import { configureDatetimeInputs } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("admin-applications-body", (body) => {
  const filterForm = body.querySelector("form.filters-form")!

  // Setup datetime input timezone conversion
  configureDatetimeInputs(filterForm, ["created_after", "created_before"])

  // Disable empty inputs before form submission to prevent validation errors
  filterForm.addEventListener("submit", () => {
    const inputs = filterForm.querySelectorAll("input, select")
    for (const input of inputs) {
      if (!input.value) input.disabled = true
    }
  })

  const exportVisibleButton = body.querySelector("button.export-visible-btn")!
  exportVisibleButton.addEventListener("click", async () => {
    const appIds = Array.from(
      body.querySelectorAll("tr[data-app-id]"),
      (el) => el.dataset.appId,
    )
    const json = `[${appIds.join(",")}]`

    try {
      await navigator.clipboard.writeText(json)
    } catch (error) {
      console.warn("AdminApps: Failed to copy IDs", { count: appIds.length }, error)
      alert(error.message)
    }
  })

  const exportAllButton = body.querySelector("button.export-all-btn")!
  exportAllButton.addEventListener("click", () => {
    const a = document.createElement("a")
    a.href = `/api/web/admin/applications/export${window.location.search}`
    a.download = ""
    document.body.append(a)
    a.click()
    a.remove()
  })

  configureStandardPagination(body, {
    loadCallback: (renderContainer) => {
      configureBootstrapTooltips(renderContainer)
      configureBootstrapPopovers(renderContainer)
    },
  })
})
