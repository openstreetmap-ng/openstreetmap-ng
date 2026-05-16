import { StandardForm } from "@components/standard-form"
import { Service, Target, type UpdateRequest } from "@proto/user_subscription_pb"
import { useDisposeEffect } from "@utils/dispose-scope"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { render } from "preact"
import { useRef } from "preact/hooks"

// Match `/changeset/123/unsubscribe`, `/diary/456/unsubscribe`, `/note/789/unsubscribe`.
// The host route handler already validates that the user is actively subscribed
// before letting the URL render — anything reaching this regex is legitimate.
const UNSUBSCRIBE_PATH_RE = /^\/(changeset|diary|note)\/(\d+)\/unsubscribe\/?$/

const UnsubscribeModal = ({
  target,
  targetId,
}: {
  target: keyof typeof Target
  targetId: bigint
}) => {
  const modalRef = useRef<HTMLDivElement>(null)
  const redirectHref = `/${target}/${targetId}`

  useDisposeEffect((scope) => {
    const el = modalRef.current
    if (!el) return
    const modal = new Modal(el, { backdrop: "static" })
    // Closing the modal ("No, keep me updated" or X) returns to the canonical
    // URL without a reload — the SPA already rendered the underlying resource
    // (the `/.../unsubscribe` route serves the same HTML as `/.../{id}`), so
    // only the URL needs cleanup. No state change → no reactive update needed.
    scope.dom(el, "hide.bs.modal", () => {
      history.replaceState(null, "", redirectHref)
    })
    modal.show()
  })

  return (
    <div
      ref={modalRef}
      class="modal fade"
      tabIndex={-1}
      aria-hidden="true"
    >
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content border-0 shadow">
          <div class="modal-header border-bottom-0 pb-0">
            <h5 class="modal-title fs-4 text-primary">
              <i class="bi bi-bookmark-dash me-2" />
              {t("javascripts.changesets.show.unsubscribe")}
            </h5>
            <button
              type="button"
              class="btn-close"
              aria-label={t("javascripts.close")}
              data-bs-dismiss="modal"
            />
          </div>

          <div class="modal-body pt-2">
            <p class="fs-5 mb-3">
              {t(
                "subscription.would_you_like_to_unsubscribe_from_this_type_discussion",
                { type: target },
              )}
            </p>
            <div class="d-flex p-3 bg-body-tertiary rounded-3 mb-2">
              <div class="me-3 text-primary fs-4">
                <i class="bi bi-info-circle" />
              </div>
              <div class="small">
                <p class="mb-1">{t("subscription.if_you_unsubscribe.title")}:</p>
                <ul class="mb-0 ps-3">
                  <li>{t("subscription.if_you_unsubscribe.no_notifications")}</li>
                  <li>{t("subscription.if_you_unsubscribe.can_still_participate")}</li>
                  <li>{t("subscription.if_you_unsubscribe.can_resubscribe")}</li>
                </ul>
              </div>
            </div>
          </div>

          <div class="modal-footer border-top-0 pt-0">
            <div class="d-flex gap-2 w-100">
              <button
                type="button"
                class="btn btn-secondary flex-fill"
                data-bs-dismiss="modal"
              >
                {t("subscription.no_keep_me_updated")}
              </button>
              <StandardForm
                class="flex-fill"
                method={Service.method.update}
                buildRequest={(): UpdateRequest => ({
                  $typeName: "user_subscription.UpdateRequest",
                  target: Target[target],
                  targetId,
                  isSubscribed: false,
                })}
                onSuccess={(_, ctx) => ctx.redirect(redirectHref)}
              >
                <button
                  type="submit"
                  class="btn btn-primary w-100"
                >
                  {t("subscription.yes_unsubscribe_me")}
                </button>
              </StandardForm>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const match = UNSUBSCRIBE_PATH_RE.exec(window.location.pathname)
if (match) {
  const root = document.createElement("div")
  document.body.append(root)
  render(
    <UnsubscribeModal
      target={match[1] as keyof typeof Target}
      targetId={BigInt(match[2]!)}
    />,
    root,
  )
}
