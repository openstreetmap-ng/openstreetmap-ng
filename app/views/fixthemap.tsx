import { encodeMapState, parseLonLatZoom } from "@map/state"
import { PageSchema } from "@proto/fixthemap_pb"
import { config } from "@utils/config"
import { stripSpecial } from "@utils/format"
import { tRich } from "@utils/i18n"
import { mountProtoPage } from "@utils/proto-page"
import { qsParse } from "@utils/qs"
import { t } from "i18next"

const buildNoteHref = () => {
  const params = qsParse(window.location.search)
  // oxlint-disable-next-line typescript/no-unnecessary-condition
  params.zoom ??= "17"
  const at = parseLonLatZoom(params)
  return at
    ? `/note/new${encodeMapState({ ...at, layersCode: params.layers ?? "" })}`
    : "/note/new"
}

mountProtoPage(PageSchema, () => {
  const isSignedIn = config.userConfig !== undefined
  const noteHref = buildNoteHref()

  return (
    <>
      <div class="content-header">
        <h1 class="container">{t("site.fixthemap.title")}</h1>
      </div>
      <div class="content-body">
        <div class="container">
          <h3>{t("site.help.welcome.title")}</h3>
          <p class="lead mb-4">{t("layouts.intro_text")}</p>

          <h3 class="mb-3">{t("site.fixthemap.how_to_help.title")}</h3>
          <div class="row row-cols-md-2 g-3 mb-4">
            <div>
              <div class="card h-100 bg-transparent">
                <div class="card-body">
                  <h5 class="card-title">
                    {t("site.fixthemap.how_to_help.join_the_community.title")}
                  </h5>
                  <p class="card-text">
                    {t(
                      "site.fixthemap.how_to_help.join_the_community.explanation_html",
                    )}
                  </p>
                  <div class="text-center">
                    <a
                      class="btn btn-primary px-4 fw-medium"
                      href={isSignedIn ? "/?edit_help=1" : "/signup"}
                    >
                      {t("layouts.start_mapping")}
                    </a>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div class="card h-100 bg-transparent">
                <div class="card-body">
                  <h5 class="card-title">
                    {stripSpecial(t("site.welcome.add_a_note.title"))}
                  </h5>
                  <p class="mb-0">{t("site.welcome.add_a_note.para_1")}</p>
                  <p class="card-text">
                    {tRich(
                      "site.fixthemap.how_to_help.add_a_note.instructions_1_html",
                      {
                        map_link: <></>,
                        note_icon: (
                          <a
                            href={noteHref}
                            class="note-link"
                          >
                            <img
                              class="icon new-note"
                              src="/static/img/controls/_generated/new-note.webp"
                              alt={t("alt.new_note_icon")}
                            />
                          </a>
                        ),
                      },
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <h3>{t("site.fixthemap.other_concerns.title")}</h3>
          <p>
            {tRich("site.fixthemap.other_concerns.concerns_html", {
              copyright_link: (
                <a
                  href="/copyright"
                  rel="license"
                >
                  {t("site.fixthemap.other_concerns.copyright")}
                </a>
              ),
              working_group_link: (
                <a href="https://osmfoundation.org/wiki/Working_Groups">
                  {t("site.fixthemap.other_concerns.working_group")}
                </a>
              ),
            })}
          </p>

          <h3>{t("site.any_questions.title")}</h3>
          <div class="d-flex">
            <div class="flex-shrink-0">
              <i class="bi bi-question-circle-fill text-primary fs-1" />
            </div>
            <p class="flex-grow-1 ms-3">
              {tRich("site.any_questions.paragraph_1_html", {
                help_link: <a href="/help">{t("site.any_questions.get_help_here")}</a>,
                welcome_mat_link: (
                  <a href="https://welcome.openstreetmap.org">
                    {t("site.any_questions.welcome_mat")}
                  </a>
                ),
              })}
            </p>
          </div>
        </div>
      </div>
    </>
  )
})
