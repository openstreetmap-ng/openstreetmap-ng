import { Tooltip } from "bootstrap"
import { qsEncode, qsParse } from "./_qs.js"
import { configureRemoteEditButton } from "./_remote-edit.js"
import "./_types.js"
import { isHrefCurrentPage } from "./_utils.js"
import { routerNavigateStrict } from "./index/_router.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const minEditZoom = 13
const navbar = document.querySelector(".navbar")
const editGroup = navbar.querySelector(".edit-group")
const loginLinks = navbar.querySelectorAll("a[href='/login']")

// Configure the remote edit button (JOSM)
const remoteEditButton = navbar.querySelector(".remote-edit")
if (remoteEditButton) configureRemoteEditButton(remoteEditButton)

// Add active class to current nav-lik
const navLinks = navbar.querySelectorAll(".nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

// Check for remembering user's choice before switching to the editor
const editButtons = navbar.querySelectorAll(".dropdown-item.edit-link")
const rememberChoice = navbar.querySelector("input[name='remember-choice']");

const setDefaultEditor = (event) => {
    if (!rememberChoice.checked) return;

    const editorButton = event.currentTarget;
    const userSettings = new FormData()
    userSettings.append("editor", editorButton.dataset.osmEditor)
    const response = fetch("/api/web/user/settings/editor", {
        method: "POST",
        body: userSettings
    });

    const defaultEditorBadge = editGroup.querySelector("span.badge.default-editor");
    defaultEditorBadge.remove();
    editorButton.insertAdjacentElement("beforeend", defaultEditorBadge);
}

for (const editButton of editButtons) {
    editButton.addEventListener("click", setDefaultEditor);
}

// Uncheck "remember my choice" checkbox when edit dropdown hides
const uncheckRememberChoice = () => {
    rememberChoice.checked = false;
}
editGroup.addEventListener("hidden.bs.dropdown", uncheckRememberChoice);


/**
 * Map of navbar elements to their base href
 * @type {Map<HTMLElement, string>}
 */
const mapLinksHrefMap = Array.from(navbar.querySelectorAll(".map-link")).reduce(
    (map, link) => map.set(link, link.href),
    new Map(),
)

/**
 * Update the login links with the current path and hash
 * @param {string} hash Current URL hash
 * @returns {void}
 */
const updateLoginLinks = (hash) => {
    const loginLinkQuery = qsEncode({ referer: location.pathname })
    const loginHref = `/login?${loginLinkQuery}${hash}`
    for (const link of loginLinks) link.href = loginHref
}

/**
 * Handle remote edit path (/edit?editor=remote).
 * Simulate a click on the remote edit button and navigate back to index.
 * @returns {void}
 */
export const handleEditRemotePath = () => {
    if (location.pathname !== "/edit" || !remoteEditButton) return

    const searchParams = qsParse(location.search.substring(1))
    if (searchParams.editor !== "remote") return

    console.debug("handleEditRemotePath")
    routerNavigateStrict("/")
    remoteEditButton.click()
}

// TODO: wth object support?
/**
 * Update the navbar links and current URL hash
 * @param {MapState} state Map state object
 * @param {OSMObject|null} object Optional OSM object
 * @returns {void}
 */
export const updateNavbarAndHash = (state, object = null) => {
    const isEditDisabled = state.zoom < minEditZoom
    const hash = encodeMapState(state)
    updateLoginLinks(hash)

    for (const [link, baseHref] of mapLinksHrefMap) {
        const isEditLink = link.classList.contains("edit-link")
        if (isEditLink) {
            // Remote edit button stores information in dataset
            const isRemoteEditButton = link.classList.contains("remote-edit")
            if (isRemoteEditButton) {
                link.dataset.remoteEdit = JSON.stringify({ state, object })
            } else if (object) {
                link.href = `${baseHref}?${object.type}=${object.id}${hash}`
            } else {
                link.href = baseHref + hash
            }

            // Enable/disable edit links based on current zoom level
            if (isEditDisabled) {
                if (!link.classList.contains("disabled")) {
                    link.classList.add("disabled")
                    link.ariaDisabled = "true"
                }
            } else {
                // biome-ignore lint/style/useCollapsedElseIf: Readability
                if (link.classList.contains("disabled")) {
                    link.classList.remove("disabled")
                    link.ariaDisabled = "false"
                }
            }
        } else {
            link.href = baseHref + hash
        }
    }

    // Toggle tooltip on edit group
    if (isEditDisabled) {
        if (!editGroup.classList.contains("disabled")) {
            editGroup.classList.add("disabled")
            editGroup.ariaDisabled = "true"
            Tooltip.getOrCreateInstance(editGroup, {
                title: editGroup.dataset.bsTitle,
                placement: "bottom",
            }).enable()
        }
    } else {
        // biome-ignore lint/style/useCollapsedElseIf: Readability
        if (editGroup.classList.contains("disabled")) {
            editGroup.classList.remove("disabled")
            editGroup.ariaDisabled = "false"
            Tooltip.getInstance(editGroup).disable()
        }
    }

    history.replaceState(null, "", hash)
}

// On window mapState message, update the navbar and hash
const onMapState = (data) => {
    const { lon, lat, zoom } = data.state
    updateNavbarAndHash({ lon, lat, zoom: Math.floor(zoom), layersCode: "" })
}

// Handle mapState window messages (from iD/Rapid)
addEventListener("message", (event) => {
    const data = event.data
    if (data.type === "mapState") onMapState(data)
})

// Initial update to update the login links
updateLoginLinks(location.hash)
