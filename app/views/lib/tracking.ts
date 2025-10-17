import {
    addIntegration,
    browserTracingIntegration,
    feedbackIntegration,
    init as SentryInit,
    setUser,
    type User,
} from "@sentry/browser"
import { activityTracking, config, crashReporting } from "./config"
import { getTimezoneName } from "./format"
import { themeStorage } from "./local-storage"

if (crashReporting) {
    console.debug("Enabling crash reporting")
    const userConfig = config.userConfig
    const sentryConfig = config.sentryConfig

    const tracePropagationTargets: (string | RegExp)[] = [/^\/(?!static)/]
    if (config.apiUrl !== window.location.origin) {
        tracePropagationTargets.push(config.apiUrl)
    }
    console.debug("Sentry trace propagation targets", tracePropagationTargets)

    SentryInit({
        dsn: sentryConfig.dsn,
        release: config.version,
        environment: window.location.host,
        tracesSampleRate: sentryConfig.tracesSampleRate,
        tracePropagationTargets: tracePropagationTargets,
        skipBrowserExtensionCheck: true,
        integrations: [browserTracingIntegration()],
    })

    const userInfo: User = {
        id: userConfig?.id?.toString(),
        username: userConfig?.displayName,
        ip_address: "{{auto}}",
        geo: {
            region: getTimezoneName(),
        },
    }
    console.debug("Providing user information", userInfo)
    setUser(userInfo)

    if (config.env === "test") {
        console.debug("Enabling feedback integration")
        const appTheme = themeStorage.get()
        addIntegration(
            feedbackIntegration({
                triggerLabel: "Report Issue",
                formTitle: "Report an Issue",
                submitButtonLabel: "Send Report",
                messagePlaceholder:
                    "What's the problem? How to reproduce it? What's the expected behavior?",
                colorScheme: appTheme === "auto" ? "system" : appTheme,
                themeDark: { background: "#212529" },
            }),
        )
    }
}

if (activityTracking) {
    console.debug("Enabling activity tracking")
    // @ts-expect-error
    window._paq = window._paq || []
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
