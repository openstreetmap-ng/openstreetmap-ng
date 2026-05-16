import { StandardForm } from "@components/standard-form"
import type { Signal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { Service } from "@proto/settings_pb"
import type { UserSocialValid } from "@proto/shared_pb"
import { USER_MAX_SOCIALS } from "@utils/config"
import { useDisposeLayoutEffect } from "@utils/dispose-scope"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"
import {
  knownSocials,
  SOCIAL_OPTIONS,
  SOCIAL_OPTIONS_BY_KEY,
  socialLabelText,
  socialServiceTitle,
  type SocialValue,
} from "./_socials-helpers"

export const PROFILE_SOCIALS_MODAL_ID = "ProfileSocialsModal"

type SocialRowState = SocialValue & {
  id: number
}

const SocialRow = ({
  row,
  index,
  total,
  onServiceChange,
  onValueChange,
  onMoveUp,
  onMoveDown,
  onRemove,
}: {
  row: SocialRowState
  index: number
  total: number
  onServiceChange: (id: number, service: string) => void
  onValueChange: (id: number, value: string) => void
  onMoveUp: (id: number) => void
  onMoveDown: (id: number) => void
  onRemove: (id: number) => void
}) => {
  const inputId = useId()
  const selectedOption = SOCIAL_OPTIONS_BY_KEY.get(row.service)!

  return (
    <div class="social-row">
      <div class="d-flex align-items-center mb-1">
        <div class="btn-group btn-group-sm me-2">
          {[
            {
              title: t("socials.move_up"),
              disabled: index === 0,
              icon: "chevron-up",
              onClick: () => onMoveUp(row.id),
            },
            {
              title: t("socials.move_down"),
              disabled: index === total - 1,
              icon: "chevron-down",
              onClick: () => onMoveDown(row.id),
            },
          ].map(({ title, disabled, icon, onClick }) => (
            <button
              type="button"
              class="btn btn-secondary"
              title={title}
              disabled={disabled}
              onClick={onClick}
            >
              <i class={`bi bi-${icon}`} />
            </button>
          ))}
        </div>

        <select
          class="form-select form-select-sm w-auto"
          aria-label={t("user.edit_socials")}
          value={row.service}
          onChange={(e) => onServiceChange(row.id, e.currentTarget.value)}
        >
          {SOCIAL_OPTIONS.map((option) => (
            <option value={option.key}>{socialServiceTitle(option)}</option>
          ))}
        </select>

        <button
          type="button"
          class="btn btn-link link-danger p-1 ms-auto"
          title={t("action.remove")}
          onClick={() => onRemove(row.id)}
        >
          <i class="bi bi-trash" />
        </button>
      </div>

      <div class="custom-input-group">
        <label for={inputId}>{socialLabelText(selectedOption)}</label>
        <input
          id={inputId}
          type={selectedOption.template !== undefined ? "text" : "url"}
          class="form-control"
          placeholder={selectedOption.placeholder}
          value={row.value}
          required
          onInput={(e) => onValueChange(row.id, e.currentTarget.value)}
        />
      </div>
    </div>
  )
}

export const SocialsModal = ({
  socials,
}: {
  socials: Signal<readonly UserSocialValid[]>
}) => {
  const labelId = useId()
  const rows = useSignal<readonly SocialRowState[]>([])
  const nextId = useRef(0)
  const modalRef = useRef<HTMLDivElement>(null)
  const defaultService = SOCIAL_OPTIONS[0]!.key

  const resetRows = () => {
    rows.value = knownSocials(socials.value).map((social, index) =>
      Object.assign({}, social, { id: index }),
    )
    nextId.current = rows.value.length
  }

  useDisposeLayoutEffect((scope) => {
    resetRows()
    scope.dom(modalRef.current!, "show.bs.modal", () => resetRows())
  }, [])

  const updateRow = (patch: Pick<SocialRowState, "id"> & Partial<SocialValue>) => {
    rows.value = rows.value.map((row) => {
      if (row.id !== patch.id) return row
      if (patch.service !== undefined) row.service = patch.service
      if (patch.value !== undefined) row.value = patch.value
      return row
    })
  }

  const moveRow = (id: number, direction: -1 | 1) => {
    const index = rows.value.findIndex((row) => row.id === id)
    const target = index + direction

    const next = [...rows.value]
    ;[next[index], next[target]] = [next[target]!, next[index]!]
    rows.value = next
  }

  const addRow = () => {
    if (rows.value.length >= USER_MAX_SOCIALS) return

    rows.value = [
      ...rows.value,
      {
        id: nextId.current,
        service: defaultService,
        value: "",
      },
    ]
    nextId.current += 1
  }

  const removeRow = (id: number) => {
    rows.value = rows.value.filter((row) => row.id !== id)
  }

  return (
    <div
      class="modal fade"
      id={PROFILE_SOCIALS_MODAL_ID}
      tabIndex={-1}
      aria-labelledby={labelId}
      aria-hidden="true"
      ref={modalRef}
    >
      <div class="modal-dialog">
        <StandardForm
          class="modal-content"
          method={Service.method.updateSocials}
          buildRequest={() => ({
            socials: rows.value.map(({ service, value }) => ({ service, value })),
          })}
          onSuccess={(resp) => {
            socials.value = resp.socials
            Modal.getOrCreateInstance(modalRef.current!).hide()
          }}
        >
          <div class="modal-header">
            <h5
              class="modal-title"
              id={labelId}
            >
              {t("user.edit_socials")}
            </h5>
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              data-bs-dismiss="modal"
            />
          </div>

          <div class="modal-body">
            <div class="socials-container">
              {rows.value.map((row, index) => (
                <SocialRow
                  key={row.id}
                  row={row}
                  index={index}
                  total={rows.value.length}
                  onServiceChange={(id, service) => updateRow({ id, service })}
                  onValueChange={(id, value) => updateRow({ id, value })}
                  onMoveUp={(id) => moveRow(id, -1)}
                  onMoveDown={(id) => moveRow(id, 1)}
                  onRemove={removeRow}
                />
              ))}
            </div>

            <button
              type="button"
              class="btn btn-sm btn-link"
              onClick={addRow}
              hidden={rows.value.length >= USER_MAX_SOCIALS}
            >
              <i class="bi bi-plus-lg me-1-5" />
              {t("user.add_social_link")}
            </button>
          </div>

          <div class="modal-footer">
            <button
              class="btn btn-secondary"
              type="button"
              data-bs-dismiss="modal"
            >
              {t("javascripts.close")}
            </button>
            <button
              class="btn btn-primary"
              type="submit"
            >
              {t("action.save_changes")}
            </button>
          </div>
        </StandardForm>
      </div>
    </div>
  )
}
