import { PageSchema } from "@proto/copyright_pb"
import { DEFAULT_LOCALE, primaryLanguage } from "@utils/config"
import { i18nLocale } from "@utils/i18n"
import { mountProtoPage } from "@utils/proto-page"
import type { ComponentChildren } from "preact"

const CopyrightPage = () => {
  const urlLocale = window.location.pathname.split("/").filter(Boolean)[1]
  const localeOverride =
    urlLocale && urlLocale !== primaryLanguage ? urlLocale : undefined
  const showNotice = Boolean(localeOverride) || primaryLanguage !== DEFAULT_LOCALE
  const { t, tRich } = i18nLocale(localeOverride)

  const ExtLink = ({
    href,
    children,
    rel,
  }: {
    href: string
    children: ComponentChildren
    rel?: string
  }) => (
    <a
      href={href}
      rel={rel ?? "noopener"}
    >
      {children}
    </a>
  )
  const ccBy30Link = (
    <a
      href="https://creativecommons.org/licenses/by/3.0/"
      rel="noopener"
    >
      CC BY 3.0
    </a>
  )
  const ccBy40Link = (
    <a
      href="https://creativecommons.org/licenses/by/4.0/"
      rel="noopener"
    >
      CC BY 4.0
    </a>
  )

  return (
    <>
      <div class="content-header">
        {showNotice && (
          <div class="container">
            <h1>{t("site.copyright.foreign.title")}</h1>
            <p>
              {tRich("site.copyright.foreign.html", {
                english_original_link: (
                  <a href="/copyright/en">{t("site.copyright.foreign.english_link")}</a>
                ),
              })}
            </p>
            <hr />
          </div>
        )}
        <h1 class="container">{t("site.copyright.legal_babble.title_html")}</h1>
      </div>

      <div class="content-body">
        <div class="container">
          <p>
            {tRich("site.copyright.legal_babble.introduction_1_html", {
              registered_trademark_link: (
                <a href="#trademarks">
                  <sup>®</sup>
                </a>
              ),
              open_data: (
                <i>{t("site.copyright.legal_babble.introduction_1_open_data")}</i>
              ),
              odc_odbl_link: (
                <ExtLink href="https://opendatacommons.org/licenses/odbl/">
                  {t("site.copyright.legal_babble.introduction_1_odc_odbl")}
                </ExtLink>
              ),
              osm_foundation_link: (
                <a href="https://osmfoundation.org">
                  {t("site.about.legal_1_1_openstreetmap_foundation")}
                </a>
              ),
            })}
          </p>
          <p>
            {tRich("site.copyright.legal_babble.introduction_2_html", {
              legal_code_link: (
                <ExtLink href="https://opendatacommons.org/licenses/odbl/1-0/">
                  {t("site.copyright.legal_babble.introduction_2_legal_code")}
                </ExtLink>
              ),
            })}
          </p>
          <p>
            {tRich("site.copyright.legal_babble.introduction_3_html", {
              creative_commons_link: (
                <ExtLink href="https://creativecommons.org/licenses/by-sa/2.0/">
                  {t("site.copyright.legal_babble.introduction_3_creative_commons")}
                </ExtLink>
              ),
            })}
          </p>

          <h3>{t("site.copyright.legal_babble.credit_title_html")}</h3>
          <p>{t("site.copyright.legal_babble.credit_1_html")}</p>
          <ol>
            <li>{t("site.copyright.legal_babble.credit_2_1")}</li>
            <li>{t("site.copyright.legal_babble.credit_2_2")}</li>
          </ol>
          <p>
            {tRich("site.copyright.legal_babble.credit_3_html", {
              attribution_guidelines_link: (
                <a href="https://osmfoundation.org/wiki/Licence/Attribution_Guidelines">
                  {t("site.copyright.legal_babble.credit_3_attribution_guidelines")}
                </a>
              ),
            })}
          </p>
          <p>
            {tRich("site.copyright.legal_babble.credit_4_1_html", {
              this_copyright_page_link: (
                <a href="/copyright">
                  {t("site.copyright.legal_babble.credit_4_1_this_copyright_page")}
                </a>
              ),
            })}
          </p>
          <img
            class="img-thumbnail mb-3"
            src="/static/img/copyright/attribution-example.webp"
            alt={t("site.copyright.legal_babble.attribution_example.title")}
          />

          <h3>{t("site.copyright.legal_babble.more_title_html")}</h3>
          <p>
            {tRich("site.copyright.legal_babble.more_1_1_html", {
              osmf_licence_page_link: (
                <a href="https://osmfoundation.org/wiki/Licence">
                  {t("site.copyright.legal_babble.more_1_1_osmf_licence_page")}
                </a>
              ),
            })}
          </p>
          <p>
            {tRich("site.copyright.legal_babble.more_2_1_html", {
              api_usage_policy_link: (
                <a href="https://operations.osmfoundation.org/policies/api/">
                  {t("site.copyright.legal_babble.more_2_1_api_usage_policy")}
                </a>
              ),
              tile_usage_policy_link: (
                <a href="https://operations.osmfoundation.org/policies/tiles/">
                  {t("site.copyright.legal_babble.more_2_1_tile_usage_policy")}
                </a>
              ),
              nominatim_usage_policy_link: (
                <a href="https://operations.osmfoundation.org/policies/nominatim/">
                  {t("site.copyright.legal_babble.more_2_1_nominatim_usage_policy")}
                </a>
              ),
            })}
          </p>

          <h3>{t("site.copyright.legal_babble.contributors_title_html")}</h3>
          <p>{t("site.copyright.legal_babble.contributors_intro_html")}</p>
          <ul>
            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_at_credit_html", {
                austria: (
                  <b>{t("site.copyright.legal_babble.contributors_at_austria")}</b>
                ),
                stadt_wien_link: (
                  <ExtLink href="https://www.data.gv.at/auftritte/?organisation=stadt-wien">
                    {t("site.copyright.legal_babble.contributors_at_stadt_wien")}
                  </ExtLink>
                ),
                cc_by_link: ccBy30Link,
                land_vorarlberg_link: (
                  <ExtLink href="https://vorarlberg.at/-/digitale-katastralmappe-dkm">
                    {t("site.copyright.legal_babble.contributors_at_land_vorarlberg")}
                  </ExtLink>
                ),
                cc_by_at_with_amendments_link: (
                  <ExtLink href="https://www.tirol.gv.at/data/nutzungsbedingungen/">
                    {t(
                      "site.copyright.legal_babble.contributors_at_cc_by_at_with_amendments",
                    )}
                  </ExtLink>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_au_credit_html", {
                australia: (
                  <b>{t("site.copyright.legal_babble.contributors_au_australia")}</b>
                ),
                geoscape_australia_link: (
                  <ExtLink href="https://geoscape.com.au/legal/data-copyright-and-disclaimer/">
                    {t(
                      "site.copyright.legal_babble.contributors_au_geoscape_australia",
                    )}
                  </ExtLink>
                ),
                cc_licence_link: ccBy40Link,
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_ca_credit_html", {
                canada: (
                  <b>{t("site.copyright.legal_babble.contributors_ca_canada")}</b>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_cz_credit_html", {
                czechia: (
                  <b>{t("site.copyright.legal_babble.contributors_cz_czechia")}</b>
                ),
                cc_licence_link: ccBy40Link,
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_fi_credit_html", {
                finland: (
                  <b>{t("site.copyright.legal_babble.contributors_fi_finland")}</b>
                ),
                nlsfi_license_link: (
                  <ExtLink href="https://www.maanmittauslaitos.fi/en/opendata-licence-version1">
                    {t("site.copyright.legal_babble.contributors_fi_nlsfi_license")}
                  </ExtLink>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_fr_credit_html", {
                france: (
                  <b>{t("site.copyright.legal_babble.contributors_fr_france")}</b>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_nl_credit_html", {
                netherlands: (
                  <b>{t("site.copyright.legal_babble.contributors_nl_netherlands")}</b>
                ),
                and_link: <ExtLink href="https://www.and.com/">www.and.com</ExtLink>,
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_nz_credit_html", {
                new_zealand: (
                  <b>{t("site.copyright.legal_babble.contributors_nz_new_zealand")}</b>
                ),
                linz_data_service_link: (
                  <ExtLink href="https://data.linz.govt.nz/">
                    {t("site.copyright.legal_babble.contributors_nz_linz_data_service")}
                  </ExtLink>
                ),
                cc_by_link: ccBy40Link,
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_rs_credit_html", {
                serbia: (
                  <b>{t("site.copyright.legal_babble.contributors_rs_serbia")}</b>
                ),
                rgz_link: (
                  <ExtLink href="https://web.archive.org/web/20220528220349/https://geosrbija.rs/">
                    {t("site.copyright.legal_babble.contributors_rs_rgz")}
                  </ExtLink>
                ),
                open_data_portal: (
                  <ExtLink href="https://data.gov.rs/sr/">
                    {t("site.copyright.legal_babble.contributors_rs_open_data_portal")}
                  </ExtLink>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_si_credit_html", {
                slovenia: (
                  <b>{t("site.copyright.legal_babble.contributors_si_slovenia")}</b>
                ),
                gu_link: (
                  <ExtLink href="https://www.gov.si/en/state-authorities/bodies-within-ministries/surveying-and-mapping-authority/">
                    {t("site.copyright.legal_babble.contributors_si_gu")}
                  </ExtLink>
                ),
                mkgp_link: (
                  <ExtLink href="https://www.gov.si/en/state-authorities/ministries/ministry-of-agriculture-forestry-and-food/">
                    {t("site.copyright.legal_babble.contributors_si_mkgp")}
                  </ExtLink>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_es_credit_html", {
                spain: <b>{t("site.copyright.legal_babble.contributors_es_spain")}</b>,
                ign_link: (
                  <ExtLink href="https://www.ign.es">
                    {t("site.copyright.legal_babble.contributors_es_ign")}
                  </ExtLink>
                ),
                scne_link: (
                  <ExtLink href="https://www.scne.es">
                    {t("site.copyright.legal_babble.contributors_es_scne")}
                  </ExtLink>
                ),
                cc_by_link: ccBy40Link,
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_za_credit_html", {
                south_africa: (
                  <b>{t("site.copyright.legal_babble.contributors_za_south_africa")}</b>
                ),
                ngi_link: (
                  <ExtLink href="https://ngi.dalrrd.gov.za">
                    {t("site.copyright.legal_babble.contributors_za_ngi")}
                  </ExtLink>
                ),
              })}
            </Contributor>

            <Contributor>
              {tRich("site.copyright.legal_babble.contributors_gb_credit_html", {
                united_kingdom: (
                  <b>
                    {t("site.copyright.legal_babble.contributors_gb_united_kingdom")}
                  </b>
                ),
              })}
            </Contributor>
          </ul>
          <p>
            {tRich("site.copyright.legal_babble.contributors_2_html", {
              contributors_page_link: (
                <a href="https://wiki.openstreetmap.org/wiki/Contributors">
                  {t("site.copyright.legal_babble.contributors_2_contributors_page")}
                </a>
              ),
            })}
          </p>
          <p>{t("site.copyright.legal_babble.contributors_footer_2_html")}</p>

          <h3>{t("site.copyright.legal_babble.infringement_title_html")}</h3>
          <p>{t("site.copyright.legal_babble.infringement_1_html")}</p>
          <p>
            {tRich("site.copyright.legal_babble.infringement_2_1_html", {
              takedown_procedure_link: (
                <a href="https://osmfoundation.org/wiki/Takedown_procedure">
                  {t("site.copyright.legal_babble.infringement_2_1_takedown_procedure")}
                </a>
              ),
              online_filing_page_link: (
                <a href="https://dmca.openstreetmap.org">
                  {t("site.copyright.legal_babble.infringement_2_1_online_filing_page")}
                </a>
              ),
            })}
          </p>

          <h3 id="trademarks">{t("site.copyright.legal_babble.trademarks_title")}</h3>
          <p>
            {tRich("site.copyright.legal_babble.trademarks_1_1_html", {
              trademark_policy_link: (
                <a href="https://osmfoundation.org/wiki/Trademark_Policy">
                  {t("site.copyright.legal_babble.trademarks_1_1_trademark_policy")}
                </a>
              ),
            })}
          </p>
        </div>
      </div>
    </>
  )
}

const Contributor = ({ children }: { children: ComponentChildren }) => (
  <li>{children}</li>
)

mountProtoPage(PageSchema, CopyrightPage)
