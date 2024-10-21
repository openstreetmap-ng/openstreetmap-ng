import "./_tracking.js"

import "./_i18n.js"

import "./_fixthemap.js"
import "./_id.js"
import "./_rapid.js"
import "./_welcome.js"
import { configureMainMap } from "./leaflet/_main-map.js"
import "./oauth2/_response-form-post.js"
import "./settings/_email.js"
import "./settings/_index.js"
import "./settings/_nav.js"
import "./settings/_security.js"
import "./settings/applications/_edit.js"
import "./settings/applications/_index.js"
import "./traces/_details.js"
import "./traces/_edit.js"
import "./traces/_list.js"
import "./traces/_preview.js"
import "./traces/_upload.js"
import "./user/_account-confirm.js"
import "./user/_login.js"
import "./user/_profile.js"
import "./user/_reset-password.js"
import "./user/_signup.js"
import "./user/_terms.js"

const mapContainer = document.querySelector(".main-map")
if (mapContainer) configureMainMap(mapContainer)

import "./_bootstrap.js"
import "./_copy-group.js"
import "./_rich-text.js"
