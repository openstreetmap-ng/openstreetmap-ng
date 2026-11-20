import { signal } from "@preact/signals"
import {
  changeHistoryLimit,
  parseHistoryLimit,
} from "../../../app/views/index/element-history-limit"
import { ElementHistoryRoute } from "@history-under-test"
import i18next from "i18next"
import { render } from "preact"
import translations from "@history-locale"

i18next.init({
  lng: "en",
  keySeparator: false,
  resources: { en: { translation: translations } },
  initImmediate: false,
})
window.calls = []
window.parseHistoryLimit = parseHistoryLimit
window.changeHistoryLimit = changeHistoryLimit
render(
  <ElementHistoryRoute.Component
    map={{}}
    type={signal("node")}
    id={signal(1n)}
  />,
  document.querySelector("main")!,
)
