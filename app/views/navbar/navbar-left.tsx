import { IndexRoute } from "@index/index"
import { routerNavigate } from "@index/router"
import { useDisposeEffect } from "@lib/dispose-scope"
import { type Editor, preferredEditorStorage } from "@lib/local-storage"
import { encodeMapState, getInitialMapState, type MapState } from "@lib/map/state"
import { getSearchParam } from "@lib/qs"
import { RemoteEditButton } from "@lib/remote-edit"
import type { OSMObject } from "@lib/types"
import { batch, computed, signal, useSignalEffect } from "@preact/signals"
import { Dropdown, Tooltip } from "bootstrap"
import { t } from "i18next"
import { createRef, render } from "preact"
import { useEffect, useRef } from "preact/hooks"

const MIN_EDIT_ZOOM = 13

const hasMainMap = document.getElementById("MainMap")?.tagName === "DIV"

const currentMapState = signal(getInitialMapState())
const currentObject = signal<OSMObject>()
const remoteButtonRef = createRef<HTMLButtonElement>()

const currentHash = computed(() =>
  hasMainMap ? encodeMapState(currentMapState.value) : "",
)

const editDisabled = computed(() =>
  hasMainMap ? currentMapState.value.zoom < MIN_EDIT_ZOOM : false,
)

export const updateNavbarAndHash = (state: MapState, object?: OSMObject) => {
  const hash = encodeMapState(state)
  window.history.replaceState(null, "", hash)
  batch(() => {
    currentMapState.value = state
    currentObject.value = object
  })
}

export const handleEditRemotePath = () => {
  if (location.pathname === "/edit" && getSearchParam("editor") === "remote") {
    console.debug("NavbarLeft: Handle edit remote path")
    routerNavigate(IndexRoute)
    remoteButtonRef.current!.click()
  }
}

const buildEditHref = (editor: Editor) => {
  const url = new URL("/edit", window.location.origin)
  url.searchParams.set("editor", editor)

  const object = currentObject.value
  if (object) url.searchParams.set(object.type, String(object.id))

  return url.pathname + url.search + currentHash.value
}

const EditorImg = ({
  editor,
  variant,
  className = "",
}: {
  editor: Editor
  variant: "primary" | "dropdown"
  className?: string
}) => {
  let src: string
  let name: string

  if (editor === "id") {
    src = "/static/img/brand/id.webp"
    name = "iD"
    className += " dark-filter-invert"
  } else if (editor === "rapid") {
    src = "/static/img/brand/rapid.webp"
    name = "Rapid"
  } else {
    src = "/static/img/brand/josm.webp"
    name = "JOSM"
  }

  return (
    <img
      class={className}
      src={src}
      alt={t("alt.logo", { name })}
      loading={variant === "dropdown" ? "lazy" : undefined}
    />
  )
}

const NavbarLeft = () => {
  const dropdownRootRef = useRef<HTMLDivElement>(null)
  const dropdownToggleRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<Dropdown | null>(null)
  const tooltipRef = useRef<Tooltip | null>(null)
  const rememberChoiceRef = useRef<HTMLInputElement>(null)

  // Effect: initialize dropdown
  useEffect(() => {
    dropdownRef.current = new Dropdown(dropdownToggleRef.current!, {
      autoClose: "outside",
    })
    return () => dropdownRef.current!.dispose()
  }, [])

  // Effect: initialize tooltip
  useEffect(() => {
    const tooltip = new Tooltip(dropdownRootRef.current!, {
      title: t("javascripts.site.edit_disabled_tooltip"),
      placement: "bottom",
    })
    tooltip.disable()
    tooltipRef.current = tooltip
    return () => tooltip.dispose()
  }, [])

  // Effect: hide dropdown when edit is disabled
  useSignalEffect(() => {
    if (!editDisabled.value) return

    const toggle = dropdownToggleRef.current!
    const prevDisabled = toggle.disabled
    if (prevDisabled) toggle.disabled = false
    dropdownRef.current!.hide()
    if (prevDisabled) toggle.disabled = true
  })

  // Effect: uncheck "remember my choice" when dropdown closes
  useDisposeEffect((scope) => {
    scope.dom(dropdownRootRef.current!, "hidden.bs.dropdown", () => {
      const checkbox = rememberChoiceRef.current
      if (checkbox) checkbox.checked = false
    })
  }, [])

  // Effect: toggle tooltip based when edit is disabled/enabled
  useSignalEffect(() => {
    const tooltip = tooltipRef.current!
    if (editDisabled.value) {
      tooltip.enable()
    } else {
      tooltip.disable()
      tooltip.hide()
    }
  })

  const onSelectEditor = (editor: Editor) => {
    if (rememberChoiceRef.current?.checked) {
      preferredEditorStorage.value = editor
    }
    dropdownRef.current!.hide()
  }

  const disabled = editDisabled.value
  return (
    <>
      <div
        class={`btn-group edit-group flex-grow-1 ${disabled ? "disabled" : ""}`}
        aria-disabled={disabled}
        ref={dropdownRootRef}
      >
        <a
          class={`btn edit-link default ${disabled ? "disabled" : ""}`}
          href={disabled ? undefined : buildEditHref(preferredEditorStorage.value)}
          aria-disabled={disabled}
          tabIndex={disabled ? -1 : undefined}
        >
          {t("layouts.edit")}
          <EditorImg
            editor={preferredEditorStorage.value}
            variant="primary"
          />
        </a>

        <button
          class="btn dropdown-toggle dropdown-toggle-split"
          type="button"
          data-bs-toggle="dropdown"
          data-bs-auto-close="outside"
          aria-expanded="false"
          aria-label={t("editor.toggle_editor_selection")}
          disabled={disabled}
          ref={dropdownToggleRef}
        />

        <div class="dropdown-menu dropdown-menu-green">
          {disabled || (
            <>
              <a
                class="dropdown-item edit-link"
                href={buildEditHref("id")}
                onClick={() => onSelectEditor("id")}
              >
                <EditorImg
                  editor="id"
                  variant="dropdown"
                />
                {t("layouts.edit_with", { editor: t("editor.id.description") })}
              </a>

              <a
                class="dropdown-item edit-link"
                href={buildEditHref("rapid")}
                onClick={() => onSelectEditor("rapid")}
              >
                <EditorImg
                  editor="rapid"
                  variant="dropdown"
                />
                {t("layouts.edit_with", { editor: t("editor.rapid.name") })}
              </a>

              <RemoteEditButton
                buttonRef={remoteButtonRef}
                class="dropdown-item edit-link"
                onBeforeOpen={() => onSelectEditor("remote")}
                state={currentMapState}
                object={currentObject}
              >
                <EditorImg
                  editor="remote"
                  variant="dropdown"
                />
                {t("layouts.edit_with", { editor: t("editor.remote.description") })}
              </RemoteEditButton>

              <hr class="dropdown-divider" />

              <div class="form-check mx-3">
                <label class="form-check-label">
                  <input
                    class="form-check-input"
                    type="checkbox"
                    name="remember-choice"
                    ref={rememberChoiceRef}
                  />
                  {t("action.remember_my_choice")}
                </label>
              </div>
            </>
          )}
        </div>
      </div>

      <a
        class="btn"
        href={`/history${currentHash.value}`}
      >
        {t("layouts.history")}
      </a>

      <a
        class="btn"
        href={`/export${currentHash.value}`}
      >
        {t("site.export.title")}
      </a>
    </>
  )
}

const navbarLeftRoot = document.getElementById("NavbarLeft")
if (navbarLeftRoot) render(<NavbarLeft />, navbarLeftRoot)
