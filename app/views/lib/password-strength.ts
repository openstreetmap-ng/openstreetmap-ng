import { toHex } from "@lib/hex"
import { sha1 } from "@noble/hashes/legacy.js"
import { effect, signal } from "@preact/signals-core"
import i18next from "i18next"

type StrengthLevelKey = "weak" | "fair" | "good" | "strong" | "perfect"

type SuggestionKey =
    | "min_length"
    | "add_more_characters"
    | "add_lowercase"
    | "add_uppercase"
    | "add_numbers"
    | "add_symbols"
    | "avoid_repeats"
    | "pwned_password"

interface EvaluateOptions {
    minLength: number
    idealLength: number
}

interface StrengthLevel {
    key: StrengthLevelKey
    minScore: number
}

interface StrengthResult {
    score: number
    level: StrengthLevel
    suggestions: SuggestionKey[]
}

const STRENGTH_LEVELS: StrengthLevel[] = [
    { key: "weak", minScore: 0 },
    { key: "fair", minScore: 40 },
    { key: "good", minScore: 60 },
    { key: "strong", minScore: 80 },
    { key: "perfect", minScore: 95 },
]

const LOWERCASE_REGEX = /[a-z]/
const UPPERCASE_REGEX = /[A-Z]/
const NUMBER_REGEX = /\d/
const SYMBOL_REGEX = /[^A-Za-z0-9]/
const STRENGTH_LENGTH_WEIGHT = 0.5
const STRENGTH_COMPLEXITY_WEIGHT = 0.45
const STRENGTH_DIVERSITY_WEIGHT = 0.05
const PWNED_PASSWORD_CHECK_DELAY = 750
const PWNED_PASSWORD_CACHE = new Map<string, boolean>()

let hintIdCounter = 0

const evaluateStrength = (
    password: string,
    { minLength, idealLength }: EvaluateOptions,
): StrengthResult => {
    const length = password.length
    const hasLowercase = LOWERCASE_REGEX.test(password)
    const hasUppercase = UPPERCASE_REGEX.test(password)
    const hasNumber = NUMBER_REGEX.test(password)
    const hasSymbol = SYMBOL_REGEX.test(password)
    const isCompromised = PWNED_PASSWORD_CACHE.get(password)

    const categoryCount =
        Number(hasLowercase) +
        Number(hasUppercase) +
        Number(hasNumber) +
        Number(hasSymbol) +
        Number(!isCompromised)

    let lengthNormalized = Math.min(length, idealLength) / idealLength
    if (length < minLength) lengthNormalized *= length / minLength

    const categoryNormalized = categoryCount <= 1 ? 0 : (categoryCount - 1) / 3
    const characterSpace =
        (hasLowercase ? 26 : 0) +
        (hasUppercase ? 26 : 0) +
        (hasNumber ? 10 : 0) +
        (hasSymbol ? 33 : 0)
    const poolNormalized =
        Math.log2(Math.max(characterSpace, 2)) / Math.log2(26 + 26 + 10 + 33)
    const complexityNormalized = (categoryNormalized + poolNormalized) / 2

    const uniqueRatio = length ? new Set(password).size / length : 0
    const uniqueNormalized = Math.max(0, Math.min(1, (uniqueRatio - 0.5) / 0.5))

    const score = isCompromised
        ? 5
        : Math.round(
              Math.max(
                  0,
                  Math.min(
                      1,
                      lengthNormalized * STRENGTH_LENGTH_WEIGHT +
                          complexityNormalized * STRENGTH_COMPLEXITY_WEIGHT +
                          uniqueNormalized * STRENGTH_DIVERSITY_WEIGHT,
                  ),
              ) * 100,
          )

    let level = STRENGTH_LEVELS[0]
    for (const strengthLevel of STRENGTH_LEVELS) {
        if (score >= strengthLevel.minScore) level = strengthLevel
    }

    const suggestions = new Set<SuggestionKey>()
    if (isCompromised) suggestions.add("pwned_password")
    if (length < minLength) suggestions.add("min_length")
    else if (length < idealLength) suggestions.add("add_more_characters")
    if (!hasLowercase) suggestions.add("add_lowercase")
    if (!hasUppercase) suggestions.add("add_uppercase")
    if (!hasNumber) suggestions.add("add_numbers")
    if (!hasSymbol) suggestions.add("add_symbols")
    if (length >= minLength && uniqueRatio > 0 && uniqueRatio < 2 / 3)
        suggestions.add("avoid_repeats")

    // Only allow "perfect" when there are no suggestions; otherwise cap at "strong"
    if (level.key === "perfect" && suggestions.size)
        level = STRENGTH_LEVELS.find((l) => l.key === "strong")

    return { score, level, suggestions: [...suggestions] }
}

const inputs = document.querySelectorAll(
    "input[type=password][data-name=new_password], input[type=password][data-name=password][autocomplete=new-password]",
)
console.debug("Initializing", inputs.length, "password strength meters")
for (const input of inputs) {
    const minLength = input.minLength
    const idealLength = Math.max(minLength + 4, 12)

    const container = document.createElement("div")
    container.classList.add("password-strength")

    const header = document.createElement("div")
    header.classList.add("password-strength-header")
    container.append(header)

    const label = document.createElement("span")
    label.classList.add("password-strength-label")
    label.textContent = i18next.t("password_strength.password_strength")
    header.append(label)

    const status = document.createElement("span")
    status.classList.add("password-strength-status")
    status.setAttribute("aria-live", "polite")
    status.setAttribute("role", "status")
    header.append(status)

    const progress = document.createElement("div")
    progress.classList.add("progress", "password-strength-progress")
    container.append(progress)

    const progressBar = document.createElement("div")
    progressBar.classList.add("progress-bar", "password-strength-progress-bar")
    progressBar.setAttribute("role", "progressbar")
    progressBar.setAttribute("aria-valuemin", "0")
    progressBar.setAttribute("aria-valuemax", "100")
    progressBar.ariaLabel = i18next.t("password_strength.password_strength")
    progress.append(progressBar)

    const hintText = document.createElement("p")
    hintText.classList.add("password-strength-hint-text")
    container.append(hintText)

    const hintList = document.createElement("ul")
    hintList.classList.add("password-strength-hints")
    container.append(hintList)
    hintList.hidden = true

    const hintId = `password-strength-hint-${hintIdCounter++}`
    hintText.id = hintId
    const describedBy = input.getAttribute("aria-describedby")
    input.setAttribute(
        "aria-describedby",
        describedBy ? `${describedBy} ${hintId}` : hintId,
    )

    const passwordToCheck = signal("")

    const renderEmptyState = () => {
        container.dataset.level = "empty"
        progressBar.style.width = "0%"
        progressBar.setAttribute("aria-valuenow", "0")
        status.textContent = ""
        hintText.hidden = true
        hintList.replaceChildren()
        hintList.hidden = true
    }

    const update = () => {
        const password = input.value
        if (!password) {
            renderEmptyState()
            return
        }

        const { score, level, suggestions } = evaluateStrength(password, {
            minLength,
            idealLength,
        })

        container.dataset.level = level.key
        const displayedScore = level.key === "perfect" ? 100 : score
        progressBar.style.width = `${Math.max(displayedScore, 5)}%`
        progressBar.setAttribute("aria-valuenow", displayedScore.toString())

        let levelLabel: string
        switch (level.key) {
            case "weak":
                levelLabel = i18next.t("password_strength.levels.weak")
                break
            case "fair":
                levelLabel = i18next.t("password_strength.levels.fair")
                break
            case "good":
                levelLabel = i18next.t("password_strength.levels.good")
                break
            case "strong":
                levelLabel = i18next.t("password_strength.levels.strong")
                break
            case "perfect":
                levelLabel = i18next.t("password_strength.levels.perfect")
                break
            default:
                levelLabel = "?"
        }
        status.textContent = levelLabel

        if (suggestions.length) {
            hintText.hidden = false
            hintText.textContent = `${i18next.t(
                "password_strength.to_strengthen_it_you_can",
            )}:`
            hintList.hidden = false
            hintList.replaceChildren(
                ...suggestions.map((suggestion) => {
                    const item = document.createElement("li")
                    switch (suggestion) {
                        case "min_length":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.use_at_least_min_length_characters",
                                { min_length: minLength },
                            )
                            break
                        case "add_more_characters":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.add_couple_more_characters",
                            )
                            break
                        case "add_lowercase":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.include_lowercase_letters",
                            )
                            break
                        case "add_uppercase":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.include_uppercase_letters",
                            )
                            break
                        case "add_numbers":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.include_digits",
                            )
                            break
                        case "add_symbols":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.include_symbols",
                            )
                            break
                        case "avoid_repeats":
                            item.textContent = i18next.t(
                                "password_strength.suggestions.avoid_repeated_characters",
                            )
                            break
                        case "pwned_password":
                            item.classList.add("text-danger")
                            item.textContent = i18next.t(
                                "password_strength.suggestions.use_a_password_not_widely_known",
                            )
                            break
                    }
                    return item
                }),
            )
        } else {
            hintText.hidden = false
            hintText.textContent = i18next.t(
                "password_strength.great_password_nice_work",
            )
            hintList.hidden = true
            hintList.replaceChildren()
        }
    }

    let scheduledCheck: number | undefined
    const requestPwnedCheck = (immediate: boolean) => {
        window.clearTimeout(scheduledCheck)

        const password = input.value
        if (!password || immediate) {
            passwordToCheck.value = password
            return
        }

        scheduledCheck = window.setTimeout(() => {
            passwordToCheck.value = password
        }, PWNED_PASSWORD_CHECK_DELAY)
    }

    update()
    input.addEventListener("input", () => {
        passwordToCheck.value = ""
        update()
        requestPwnedCheck(false)
    })
    input.addEventListener("blur", () => requestPwnedCheck(true))
    input.form?.addEventListener("reset", () => {
        window.clearTimeout(scheduledCheck)
        passwordToCheck.value = ""
        window.setTimeout(update)
    })
    input.after(container)

    effect(() => {
        const password = passwordToCheck.value
        if (password.length < minLength) return

        const abortController = new AbortController()
        lookupPwnedPassword(password, abortController.signal)
            .then(update)
            .catch((error: Error) => {
                if (error.name === "AbortError") return
                console.error("Failed to check password safety", error)
            })

        return () => {
            abortController.abort()
        }
    })
}

const lookupPwnedPassword = async (
    password: string,
    abortSignal: AbortSignal,
): Promise<void> => {
    const cached = PWNED_PASSWORD_CACHE.get(password)
    if (cached !== undefined) return

    const hash = await sha1_hex(password)
    const prefix = hash.slice(0, 5)
    const suffix = hash.slice(5)

    const response = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`, {
        signal: abortSignal,
        headers: { "Add-Padding": "true" },
        referrerPolicy: "no-referrer",
    })
    if (!response.ok)
        throw new Error(`Failed to check password safety (${response.status})`)

    const body = await response.text()
    for (const line of body.split("\n")) {
        const [hashSuffix, occurrences] = line.split(":")
        if (hashSuffix === suffix && occurrences !== "0") {
            PWNED_PASSWORD_CACHE.set(password, true)
            return
        }
    }

    PWNED_PASSWORD_CACHE.set(password, false)
}

const sha1_hex = async (value: string): Promise<string> => {
    const data = new TextEncoder().encode(value)
    let bytes: Uint8Array
    try {
        bytes = new Uint8Array(await crypto.subtle.digest("SHA-1", data))
    } catch (e: any) {
        if (e?.name !== "NotSupportedError") throw e
        console.warn("SubtleCrypto does not support SHA-1, falling back to polyfill")
        bytes = sha1(data)
    }
    return toHex(bytes).toUpperCase()
}
