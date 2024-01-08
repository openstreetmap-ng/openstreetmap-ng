// Global dataset options are defined on <html> tag
const params = document.documentElement.dataset

// User preferred languages
export const languages = JSON.parse(params.languages)

// The first language is the most preferred
// TODO: py, only existing/installed locales
export const primaryLanguage = languages[0]

// User home location point
export const homePoint = params.homePoint
