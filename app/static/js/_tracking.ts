import { activityTracking, crashReporting } from "./_config"

const enableSentryTracking = () => {
    // TODO: sentry
}

const enableMatomoTracking = () => {
    // @ts-ignore
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

if (crashReporting) enableSentryTracking()
if (activityTracking) enableMatomoTracking()
