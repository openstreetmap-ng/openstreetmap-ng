import type { Message } from "@bufbuild/protobuf"
import { USER_DESCRIPTION_MAX_LENGTH, USER_MAX_SOCIALS } from "@lib/config"
import { useDisposeLayoutEffect } from "@lib/dispose-scope"
import { Service } from "@lib/proto/settings_pb"
import type { UserSocialValid } from "@lib/proto/shared_pb"
import { StandardForm } from "@lib/standard-form"
import type { Signal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"
import { RichTextControl } from "../../rich-text/_control"
import type { ProfileSocialOptionConfig } from "./_social-options.macro"
import { getProfileSocialOptions } from "./_social-options.macro" with { type: "macro" }

type SocialValue = Omit<UserSocialValid, keyof Message>

type SocialRowState = SocialValue & {
  id: number
}

type SocialServiceOption = ProfileSocialOptionConfig & {
  titleKey: string
  labelKey: string
}

const PROFILE_DESCRIPTION_MODAL_ID = "ProfileDescriptionModal"
const PROFILE_SOCIALS_MODAL_ID = "ProfileSocialsModal"

const SOCIAL_OPTIONS = getProfileSocialOptions() as SocialServiceOption[]
for (const option of SOCIAL_OPTIONS) {
  option.titleKey = `service.${option.key.replaceAll("-", "_")}.title`
  option.labelKey = `socials.label.${option.label}`
}
const SOCIAL_OPTIONS_BY_KEY = new Map(
  SOCIAL_OPTIONS.map((option) => [option.key, option]),
)

const knownSocials = (socials: readonly UserSocialValid[]) =>
  socials.filter((social) => SOCIAL_OPTIONS_BY_KEY.has(social.service))

const getSocialLink = (social: SocialValue, option: SocialServiceOption) => {
  const { template } = option
  if (template === undefined) return social.value
  return template ? template.replace("{}", social.value) : null
}

const SocialLinks = ({
  socials,
  class: className = "",
}: {
  socials: readonly UserSocialValid[]
  class?: string
}) => {
  if (!socials.length) return null

  return (
    <div class={`ms-1 d-flex flex-wrap gap-2 ${className}`}>
      {socials.map((social) => {
        const option = SOCIAL_OPTIONS_BY_KEY.get(social.service)!
        const serviceTitle = t(option.titleKey)
        const href = getSocialLink(social, option)
        const icon = option.icon ?? social.service

        return href ? (
          <a
            key={`${social.service}:${social.value}`}
            href={href}
            target="_blank"
            rel="noopener nofollow"
            title={serviceTitle}
            class="btn btn-sm btn-soft"
          >
            <i class={`bi bi-${icon} me-1-5`} />
            {social.value}
          </a>
        ) : (
          <span
            key={`${social.service}:${social.value}`}
            class="btn btn-sm btn-soft"
            title={serviceTitle}
          >
            <i class={`bi bi-${icon} me-1-5`} />
            {social.value}
          </span>
        )
      })}
    </div>
  )
}

export const AboutSection = ({
  isSelf,
  description,
  descriptionRich,
  socials: initialSocials,
}: {
  isSelf: boolean
  description: Signal<string | undefined>
  descriptionRich: Signal<string>
  socials: Signal<readonly UserSocialValid[]>
}) => {
  const hasDescription = Boolean(description.value)
  const socials = knownSocials(initialSocials.value)
  const hasSocials = socials.length > 0
  if (!(hasDescription || hasSocials || isSelf)) return null

  return (
    <>
      <h3 class={`ms-1 ${hasSocials ? "mb-2" : "mb-3"} d-flex align-items-center`}>
        {t("user.about_me")}
        {isSelf && (
          <>
            <button
              class="btn btn-sm btn-soft ms-3"
              type="button"
              data-bs-toggle="modal"
              data-bs-target={`#${PROFILE_SOCIALS_MODAL_ID}`}
            >
              <i class="bi bi-pencil-square me-1-5" />
              {t("user.edit_socials")}
            </button>
            <button
              class="btn btn-sm btn-soft ms-2"
              type="button"
              data-bs-toggle="modal"
              data-bs-target={`#${PROFILE_DESCRIPTION_MODAL_ID}`}
            >
              <i class="bi bi-pencil-square me-1-5" />
              {t("user.edit_description")}
            </button>
          </>
        )}
      </h3>

      <SocialLinks
        socials={socials}
        class={hasDescription || isSelf ? "mb-3" : "mb-4"}
      />

      {hasDescription ? (
        <div
          class="mb-4 ms-1 rich-text"
          dangerouslySetInnerHTML={{ __html: descriptionRich.value }}
        />
      ) : isSelf ? (
        <div class="mb-4 ms-1 form-text">
          {t("user.you_have_not_provided_a_description")}
        </div>
      ) : null}
    </>
  )
}

export const DescriptionModal = ({
  description,
  descriptionRich,
}: {
  description: Signal<string | undefined>
  descriptionRich: Signal<string>
}) => {
  const labelId = useId()
  const modalRef = useRef<HTMLDivElement>(null)

  return (
    <div
      class="modal fade"
      id={PROFILE_DESCRIPTION_MODAL_ID}
      tabIndex={-1}
      aria-labelledby={labelId}
      aria-hidden="true"
      ref={modalRef}
    >
      <div class="modal-dialog modal-lg">
        <StandardForm
          class="description-form modal-content"
          method={Service.method.updateDescription}
          buildRequest={({ formData }) => ({
            description: formData.get("description") as string,
          })}
          onSuccess={(resp) => {
            description.value = resp.description
            descriptionRich.value = resp.descriptionRich
            Modal.getOrCreateInstance(modalRef.current!).hide()
          }}
        >
          <div class="modal-header">
            <h5
              class="modal-title"
              id={labelId}
            >
              {t("user.edit_description")}
            </h5>
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              data-bs-dismiss="modal"
            />
          </div>
          <div class="modal-body">
            <RichTextControl
              name="description"
              value={description.value ?? ""}
              maxLength={USER_DESCRIPTION_MAX_LENGTH}
            />
          </div>
          <div class="modal-footer d-flex justify-content-between">
            <div>
              <p class="form-text m-0">
                {t("user.your_profile_description_is_displayed_publicly")}
              </p>
            </div>
            <div>
              <button
                class="btn btn-secondary me-2"
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
          </div>
        </StandardForm>
      </div>
    </div>
  )
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
            <option value={option.key}>{t(option.titleKey)}</option>
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
        <label for={inputId}>{t(selectedOption.labelKey)}</label>
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
