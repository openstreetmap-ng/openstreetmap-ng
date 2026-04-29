import { config } from "@lib/config"
import { mountProtoPage } from "@lib/proto-page"
import { DetailsPageSchema } from "@lib/proto/diary_pb"
import { EntryCard, EntryMeta } from "./_entry"
import { t } from "i18next"
import { DiaryTab, Nav } from "./_nav"

mountProtoPage(DetailsPageSchema, ({ entry }) => (
  <>
    <div class="content-header pb-0">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <div class="row mb-3">
          <div class="col-auto">
            <a href={`/user/${entry.user.displayName}`}>
              <img
                class="avatar"
                src={entry.user.avatarUrl}
                alt={t("alt.profile_picture")}
              />
            </a>
          </div>
          <div class="col">
            <h2>{entry.title}</h2>
            <EntryMeta
              entry={entry}
              class="small mb-0"
              showAvatar={false}
            />
          </div>
        </div>

        <Nav
          activeTab={
            config.userConfig?.user.id === entry.user.id
              ? DiaryTab.self
              : DiaryTab.profile
          }
          language={undefined}
          user={entry.user}
        />
      </div>
    </div>

    <div class="content-body">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <div class="diary-list mb-4">
          <EntryCard
            entry={entry}
            details
            profilePage
          />
        </div>
      </div>
    </div>
  </>
))
