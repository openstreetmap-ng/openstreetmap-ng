import { encodeMapState, type MapState, parseLonLatZoom } from "@map/state"
import { PageSchema } from "@proto/welcome_pb"
import { HOUR, MINUTE, SECOND } from "@std/datetime/constants"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { toTitleCase } from "@std/text/unstable-to-title-case"
import { useDisposeEffect } from "@utils/dispose-scope"
import { stripSpecial } from "@utils/format"
import { tRich } from "@utils/i18n"
import { mountProtoPage } from "@utils/proto-page"
import { qsEncode, qsParse } from "@utils/qs"
import { t } from "i18next"
import { useRef } from "preact/hooks"

const computeStartContext = () => {
  const params = qsParse(window.location.search)
  // oxlint-disable-next-line typescript/no-unnecessary-condition
  params.zoom ??= "17"
  // oxlint-disable-next-line typescript/no-unnecessary-condition
  params.layers ??= ""
  const layersCode = params.layers
  const at = parseLonLatZoom(params)
  const providedState: MapState | undefined = at ? { ...at, layersCode } : undefined

  const startParams: Record<string, string> = {}
  if (params.editor) startParams.editor = params.editor

  const noteHref = providedState
    ? `/note/new${encodeMapState(providedState)}`
    : "/note/new"

  return { providedState, startParams, layersCode, noteHref }
}

const WelcomePage = () => {
  const { providedState, startParams, layersCode, noteHref } = computeStartContext()
  const startButtonRef = useRef<HTMLAnchorElement>(null)

  // If location was provided directly via URL, use it. Otherwise try to fill
  // it in from the user's geolocation. We update the start button href so a
  // plain click still works without JS — the click handler races to capture
  // a fresh position too.
  const fallbackEditHref = `/edit${qsEncode(startParams)}`
  const initialStartHref = providedState
    ? `${fallbackEditHref}${encodeMapState(providedState)}`
    : fallbackEditHref

  useDisposeEffect((scope) => {
    if (providedState) return
    const startButton = startButtonRef.current
    if (!startButton) return

    const onGeolocationSuccess = (position: GeolocationPosition) => {
      console.debug("Welcome: Geolocation success", position)
      const geolocationState = {
        lon: position.coords.longitude,
        lat: position.coords.latitude,
        zoom: 17,
        layersCode,
      } satisfies MapState
      startButton.href = `${fallbackEditHref}${encodeMapState(geolocationState)}`
    }
    const onGeolocationFailure = () => {
      console.debug("Welcome: Geolocation failure")
    }

    scope.dom(
      startButton,
      "click",
      (e) => {
        e.preventDefault()
        navigator.geolocation.getCurrentPosition(
          (position) => {
            onGeolocationSuccess(position)
            window.location.href = startButton.href
          },
          () => {
            onGeolocationFailure()
            window.location.href = startButton.href
          },
          { maximumAge: 8 * HOUR, timeout: 10 * SECOND },
        )
      },
      { once: true },
    )

    // Permissions API is unavailable in iOS Safari < 16. lib.dom types it as
    // always present; ambient augmentation can't weaken that, so suppress the
    // resulting "unnecessary optional chain" warning.
    // oxlint-disable-next-line typescript/no-unnecessary-condition
    void navigator.permissions?.query({ name: "geolocation" }).then((result) => {
      console.debug("Welcome: Geolocation permission", result.state)
      if (result.state === "granted") {
        navigator.geolocation.getCurrentPosition(
          onGeolocationSuccess,
          onGeolocationFailure,
          { maximumAge: 8 * HOUR, timeout: MINUTE },
        )
      }
    })
  }, [])

  const realAndCurrent = <i>{t("site.welcome.whats_on_the_map.real_and_current")}</i>
  const doesnt = <i>{t("site.welcome.whats_on_the_map.doesnt")}</i>

  return (
    <>
      <div class="content-header">
        <h1 class="container">{t("site.help.welcome.title")}</h1>
      </div>
      <div class="content-body">
        <div class="container">
          <p class="lead mb-4">{t("site.welcome.introduction")}</p>

          <h3 class="mb-3">{t("site.welcome.whats_on_the_map.title")}</h3>
          <div class="row row-cols-md-2 g-3 g-md-4 mb-4">
            <div>
              <div class="card h-100 tutorial-card should">
                <div class="card-body">
                  <p class="mb-0">
                    {tRich("site.welcome.whats_on_the_map.on_the_map_html", {
                      real_and_current: realAndCurrent,
                    })}
                  </p>
                </div>
                <i class="bi bi-check-circle-fill text-green fs-5" />
              </div>
            </div>

            <div>
              <div class="card h-100 tutorial-card should-not">
                <div class="card-body">
                  <p class="mb-0">
                    {tRich("site.welcome.whats_on_the_map.off_the_map_html", {
                      doesnt,
                    })}
                  </p>
                </div>
                <i class="bi bi-x-circle-fill text-danger fs-5" />
              </div>
            </div>
          </div>

          <h3>{t("site.welcome.basic_terms.title")}</h3>
          <p>{t("site.welcome.basic_terms.paragraph_1")}</p>

          <div class="row row-cols-sm-2 row-cols-lg-4 g-3 mb-4">
            <TermCard
              icon="bi-pencil-fill"
              title={toTitleCase(t("site.welcome.basic_terms.editor"))}
              wikiHref="https://wiki.openstreetmap.org/wiki/Editors"
            >
              {tRich("site.welcome.basic_terms.an_editor_html", {
                editor: t("site.welcome.basic_terms.editor"),
              })}
            </TermCard>
            <TermCard
              icon="bi-geo-alt-fill"
              title={toTitleCase(t("javascripts.query.node"))}
              wikiHref="https://wiki.openstreetmap.org/wiki/Node"
            >
              {tRich("site.welcome.basic_terms.a_node_html", {
                node: t("javascripts.query.node").toLowerCase(),
              })}
            </TermCard>
            <TermCard
              icon="bi-sign-turn-right-fill"
              title={toTitleCase(t("javascripts.query.way"))}
              wikiHref="https://wiki.openstreetmap.org/wiki/Way"
            >
              {tRich("site.welcome.basic_terms.a_way_html", {
                way: t("javascripts.query.way").toLowerCase(),
              })}
            </TermCard>
            <TermCard
              icon="bi-tag-fill"
              title={toTitleCase(t("site.welcome.basic_terms.tag"))}
              wikiHref="https://wiki.openstreetmap.org/wiki/Tags"
            >
              {tRich("site.welcome.basic_terms.a_tag_html", {
                tag: t("site.welcome.basic_terms.tag"),
              })}
            </TermCard>
          </div>

          <h3>{stripSpecial(t("site.welcome.rules.title"))}</h3>
          <p>
            {tRich("site.welcome.rules.para_1_html", {
              imports_link: (
                <a href="https://wiki.openstreetmap.org/wiki/Import/Guidelines">
                  {t("site.welcome.rules.imports").toLowerCase()}
                </a>
              ),
              automated_edits_link: (
                <a href="https://wiki.openstreetmap.org/wiki/Automated_Edits_code_of_conduct">
                  {t("site.welcome.rules.automated_edits").toLowerCase()}
                </a>
              ),
            })}
          </p>

          <h3>{t("site.any_questions.title")}</h3>
          <p class="mb-4">
            {tRich("site.any_questions.paragraph_1_html", {
              help_link: <a href="/help">{t("site.any_questions.get_help_here")}</a>,
              welcome_mat_link: (
                <a href="https://welcome.openstreetmap.org">
                  {t("site.any_questions.welcome_mat")}
                </a>
              ),
            })}
          </p>

          <h3>{stripSpecial(t("site.welcome.add_a_note.title"))}</h3>
          <p class="mb-1">{t("site.welcome.add_a_note.para_1")}</p>
          <p class="mb-4">
            {tRich("site.fixthemap.how_to_help.add_a_note.instructions_1_html", {
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
            })}
          </p>

          <div class="text-center">
            <a
              ref={startButtonRef}
              class="start-btn btn btn-lg btn-primary px-5 fw-medium"
              href={initialStartHref}
            >
              {t("layouts.start_mapping")}
            </a>
          </div>
        </div>
      </div>
    </>
  )
}

const TermCard = ({
  icon,
  title,
  wikiHref,
  children,
}: {
  icon: string
  title: string
  wikiHref: string
  children: preact.ComponentChildren
}) => (
  <div>
    <div class="card h-100">
      <div class="card-header bg-transparent text-center text-primary fw-bold">
        <i class={`bi ${icon} me-1-5`} />
        {title}
      </div>
      <div class="card-body">
        <p class="card-text">{children}</p>
      </div>
      <div class="card-footer bg-transparent">
        <p class="small text-end mb-0">
          <a
            class="stretched-link"
            href={wikiHref}
          >
            {toSentenceCase(t("layouts.learn_more"))}
            <i class="bi bi-arrow-right-short" />
          </a>
        </p>
      </div>
    </div>
  </div>
)

mountProtoPage(PageSchema, WelcomePage)
