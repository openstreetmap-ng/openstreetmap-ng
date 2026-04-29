import { qsParse } from "@lib/qs"

export const getAuthProviderReferer = () => {
  const defaultReferrer = `${window.location.pathname}${window.location.search}`
  const params = qsParse(window.location.search)
  let referrer = params.referer ?? defaultReferrer
  if (!referrer.startsWith("/")) referrer = defaultReferrer
  return referrer
}
