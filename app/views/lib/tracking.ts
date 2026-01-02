import {
  API_URL,
  activityTracking,
  config,
  ENV,
  isCrashReportingEnabled,
  SENTRY_DSN,
  SENTRY_TRACES_SAMPLE_RATE,
  VERSION,
} from "@lib/config"
import { getTimezoneName } from "@lib/format"
import { themeStorage } from "@lib/local-storage"
import {
  addIntegration,
  browserTracingIntegration,
  feedbackIntegration,
  init as SentryInit,
  setUser,
  type User,
} from "@sentry/browser"

if (isCrashReportingEnabled(config)) {
  console.debug("Sentry: Enabling")
  const userConfig = config.userConfig

  const tracePropagationTargets: (string | RegExp)[] = [/^\/(?!static)/]
  if (API_URL !== window.location.origin) {
    tracePropagationTargets.push(API_URL)
  }
  console.debug("Sentry: Trace propagation targets", tracePropagationTargets)

  SentryInit({
    dsn: SENTRY_DSN,
    release: VERSION,
    environment: window.location.host,
    tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,
    tracePropagationTargets: tracePropagationTargets,
    skipBrowserExtensionCheck: true,
    integrations: [browserTracingIntegration()],
  })

  const userInfo: User = {
    ...(userConfig?.id && { id: userConfig.id.toString() }),
    ...(userConfig?.displayName && { username: userConfig.displayName }),
    ip_address: "{{auto}}",
    geo: {
      region: getTimezoneName(),
    },
  }
  console.debug("Sentry: User info", userInfo)
  setUser(userInfo)

  if (ENV === "test") {
    console.debug("Sentry: Feedback integration")
    addIntegration(
      feedbackIntegration({
        triggerLabel: "Report Issue",
        formTitle: "Report an Issue",
        submitButtonLabel: "Send Report",
        messagePlaceholder:
          "What's the problem? How to reproduce it? What's the expected behavior?",
        colorScheme: themeStorage.value === "auto" ? "system" : themeStorage.value,
        themeDark: { background: "#212529" },
      }),
    )
  }
}

if (activityTracking) {
  console.debug("Matomo: Enabling")
  ;(window as any)._paq ??= []
  const _paq: any[] = (window as any)._paq

  // tracker methods like "setCustomDimension" should be called before "trackPageView"
  _paq.push(["setDocumentTitle", `${location.hostname}/${document.title}`])
  _paq.push(["setDoNotTrack", true])
  _paq.push(["trackPageView"])
  _paq.push(["enableLinkTracking"])
  const url = "https://matomo.monicz.dev/"
  _paq.push(["setTrackerUrl", `${url}matomo.php`])
  _paq.push(["setSiteId", "4"])

  const newScript = document.createElement("script")
  newScript.src = `${url}matomo.js`
  newScript.defer = true
  document.head.appendChild(newScript)

  // TODO: matomogoal meta[name=matomo-goal] trackGoal layeradd, layerid
}
