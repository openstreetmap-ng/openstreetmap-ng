import { config } from "@lib/config"
import { mount } from "@lib/mount"
import { qsParse } from "@lib/qs"
import { Tooltip } from "bootstrap"
import i18next from "i18next"

/**
 * Initialize the edit_help tutorial.
 * When edit_help=1 is present in the URL and user is authenticated,
 * shows a tooltip on the edit button explaining how to start mapping.
 */
mount("map-body", () => {
    // Check for edit_help parameter
    const params = qsParse(window.location.search)
    if (!params.edit_help) return

    // Only show for authenticated users
    if (!config.userConfig) {
        console.debug("EditHelp: User not authenticated, skipping")
        return
    }

    console.debug("EditHelp: Initializing tutorial")

    // Find the edit button group in the navbar
    const editGroup = document.querySelector(".edit-group")
    if (!editGroup) {
        console.warn("EditHelp: Edit button group not found")
        return
    }

    // Get the main edit link (the default editor link)
    const editLink = editGroup.querySelector("a.edit-link.default")
    if (!editLink) {
        console.warn("EditHelp: Edit link not found")
        return
    }

    // Create and show the tooltip
    const tooltipText = i18next.t("javascripts.edit_help")
    const tooltip = new Tooltip(editLink, {
        title: tooltipText,
        placement: "bottom",
        trigger: "manual",
    })

    // Show the tooltip
    tooltip.show()
    console.debug("EditHelp: Tooltip shown")

    // Remove the query parameter from URL without reload
    const url = new URL(window.location.href)
    url.searchParams.delete("edit_help")
    window.history.replaceState({}, "", url.toString())
    console.debug("EditHelp: Query parameter removed from URL")

    // Hide tooltip on first click anywhere
    const hideTooltip = () => {
        tooltip.dispose()
        document.removeEventListener("click", hideTooltip)
        console.debug("EditHelp: Tooltip dismissed")
    }
    document.addEventListener("click", hideTooltip)
})
