import { useSignal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { union } from "@std/collections/union"
import { useEffect } from "preact/hooks"
import { primaryLanguage } from "./config"
import { getWikiData } from "./tags.macro" with { type: "macro" }

const { localeSets, wikiPages: WIKI_PAGES } = getWikiData()

const LOCALE_SETS = memoize((index: number) => new Set(localeSets[index]))

// Wiki locale prefix: "zh-hans" -> "Zh-Hans:"
const localeWikiPrefix = (locale: string) =>
  `${locale
    .split("-")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("-")}:`

// Use "" for English
const USER_LOCALES =
  primaryLanguage === "en"
    ? [{ code: "", prefix: "" }]
    : [
        { code: primaryLanguage, prefix: localeWikiPrefix(primaryLanguage) },
        { code: "", prefix: "" },
      ]

const URL_KEY_PARTS = new Set(["host", "website", "url", "source", "image"])
const URL_RE = /^https?:\/\//i
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const WIKI_ID_RE = /^[Qq][1-9]\d*$/
const WIKI_LANG_RE = /^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$/
const WIKI_LANG_VALUE_RE = /^([a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(.+)$/
const WIKIMEDIA_ENTRY_RE = /^(?:file|category):/i
const MAX_VALUE_PARTS = 10

// ============================================================
// Validation
// ============================================================

const isUrlString = (s: string) => URL_RE.test(s)
const isEmailString = (s: string) => s.length <= 254 && EMAIL_RE.test(s)
const isColorValid = (s: string) => CSS.supports("color", s)
const isWikiId = (s: string) => s.length >= 2 && WIKI_ID_RE.test(s)
const isWikimediaEntry = (s: string) => WIKIMEDIA_ENTRY_RE.test(s)

let phoneLibPromise: Promise<typeof import("libphonenumber-js/min")> | undefined

// ============================================================
// Wiki Links
// ============================================================

const getWikiUrl = (key: string, value: string | null) => {
  const localeSetIndex = WIKI_PAGES[key]?.[value ?? "*"]
  if (localeSetIndex === undefined) return null

  const availableLocales = LOCALE_SETS(localeSetIndex)
  for (const { code, prefix } of USER_LOCALES) {
    if (availableLocales.has(code)) {
      const page =
        value !== null
          ? `Tag:${encodeURIComponent(key)}=${encodeURIComponent(value)}`
          : `Key:${encodeURIComponent(key)}`
      return `https://wiki.openstreetmap.org/wiki/${prefix}${page}`
    }
  }
  return null
}

// ============================================================
// Components
// ============================================================

const PhoneLink = ({ text }: { text: string }) => {
  const uri = useSignal<string | null>(null)

  useEffect(() => {
    uri.value = null

    const abortController = new AbortController()

    phoneLibPromise ??= import("libphonenumber-js/min")
    phoneLibPromise.then(({ parsePhoneNumberFromString }) => {
      abortController.signal.throwIfAborted()
      const phone = parsePhoneNumberFromString(text)
      if (phone?.isValid()) uri.value = phone.getURI()
    })

    return () => abortController.abort()
  }, [text])

  return uri.value ? (
    <a
      class="tag-value"
      href={uri.value}
      rel="noopener"
    >
      {text}
    </a>
  ) : (
    <span class="tag-value">{text}</span>
  )
}

const WikipediaLink = ({ keyParts, text }: { keyParts: string[]; text: string }) => {
  let lang = "en"
  for (const part of keyParts) {
    if (WIKI_LANG_RE.test(part)) {
      lang = part
      break
    }
  }

  let title = text
  const match = WIKI_LANG_VALUE_RE.exec(text)
  if (match) {
    lang = match[1]
    title = match[2]
  }

  return (
    <a
      class="tag-value"
      href={`https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}`}
      rel="noopener"
    >
      {text}
    </a>
  )
}

const TagValue = ({ tagKey, text }: { tagKey: string; text: string }) => {
  const keyParts = tagKey.split(":")

  // Dispatch by key part (ordered by cost: cheap first)
  for (const part of keyParts) {
    // URL-like keys
    if (URL_KEY_PARTS.has(part) && isUrlString(text)) {
      return (
        <a
          class="tag-value"
          href={text}
          rel="noopener nofollow"
        >
          {text}
        </a>
      )
    }
    // Color
    if (part === "colour" && isColorValid(text)) {
      return (
        <span class="tag-value">
          <span
            class="color-preview"
            style={{ background: text }}
          />
          {text}
        </span>
      )
    }
    // Email
    if (part === "email" && isEmailString(text)) {
      return (
        <a
          class="tag-value"
          href={`mailto:${text}`}
          rel="noopener"
        >
          {text}
        </a>
      )
    }
    // Phone/Fax
    if (part === "phone" || part === "fax") {
      return <PhoneLink text={text} />
    }
    // Wikidata
    if (part === "wikidata" && isWikiId(text)) {
      return (
        <a
          class="tag-value"
          href={`https://www.wikidata.org/entity/${text}`}
          rel="noopener"
        >
          {text}
        </a>
      )
    }
    // Wikimedia Commons
    if (part === "wikimedia_commons" && isWikimediaEntry(text)) {
      return (
        <a
          class="tag-value"
          href={`https://commons.wikimedia.org/wiki/${encodeURIComponent(text)}`}
          rel="noopener"
        >
          {text}
        </a>
      )
    }
    // Wikipedia (special: URL first, then lang-aware link)
    if (part === "wikipedia") {
      if (isUrlString(text)) {
        return (
          <a
            class="tag-value"
            href={text}
            rel="noopener nofollow"
          >
            {text}
          </a>
        )
      }
      return (
        <WikipediaLink
          keyParts={keyParts}
          text={text}
        />
      )
    }
  }

  // Fallback: wiki link for value, or plain text
  const wikiUrl = getWikiUrl(tagKey, text)
  if (wikiUrl) {
    return (
      <a
        class="tag-value"
        href={wikiUrl}
        rel="noopener"
      >
        {text}
      </a>
    )
  }
  return <span class="tag-value">{text}</span>
}

const TagKey = ({ tagKey }: { tagKey: string }) => {
  const wikiUrl = getWikiUrl(tagKey, null)
  return wikiUrl ? (
    <a
      class="tag-value"
      href={wikiUrl}
      rel="noopener"
    >
      {tagKey}
    </a>
  ) : (
    <span class="tag-value">{tagKey}</span>
  )
}

const TagValues = ({
  tagKey,
  value,
  class: className = "tag-values",
}: {
  tagKey: string
  value: string
  class?: string
}) => (
  <div class={className}>
    {value
      .split(";")
      .slice(0, MAX_VALUE_PARTS)
      .map((part, i) => {
        const trimmed = part.trim()
        return trimmed ? (
          <TagValue
            key={i}
            tagKey={tagKey}
            text={trimmed}
          />
        ) : null
      })}
  </div>
)

interface DiffRow {
  key: string
  value: string
  oldValue: string | undefined
  status: "added" | "modified" | "deleted" | undefined // undefined = unchanged
}

const TagRow = ({
  tagKey,
  value,
  oldValue,
  status,
}: {
  tagKey: string
  value: string
  oldValue: string | undefined
  status: DiffRow["status"]
}) => (
  <tr data-status={status}>
    <td>
      <TagKey tagKey={tagKey} />
    </td>
    <td>
      {status === "modified" ? (
        <div>
          <TagValues
            tagKey={tagKey}
            value={value}
          />
          <TagValues
            tagKey={tagKey}
            value={oldValue!}
            class="tag-previous"
          />
        </div>
      ) : (
        <TagValues
          tagKey={tagKey}
          value={value}
        />
      )}
    </td>
  </tr>
)

const computeDiffRows = (
  tags: Record<string, string>,
  tagsOld: Record<string, string> | null,
  diff: boolean,
): DiffRow[] => {
  const rows: DiffRow[] = []
  const deleted: DiffRow[] = []
  const allKeys = union(Object.keys(tags), Object.keys(tagsOld ?? {})).sort((a, b) =>
    a.localeCompare(b),
  )

  for (const key of allKeys) {
    const value = tags[key]
    const oldValue = tagsOld?.[key]

    if (value !== undefined) {
      let status: DiffRow["status"]
      if (diff && tagsOld) {
        if (oldValue === undefined) status = "added"
        else if (oldValue !== value) status = "modified"
      }
      rows.push({
        key,
        value,
        oldValue: status === "modified" ? oldValue : undefined,
        status,
      })
    } else if (diff && oldValue !== undefined) {
      deleted.push({ key, value: oldValue, oldValue: undefined, status: "deleted" })
    }
  }
  return rows.concat(deleted)
}

export const Tags = ({
  tags,
  tagsOld,
  diff = false,
}: {
  tags: Record<string, string>
  tagsOld?: Record<string, string>
  diff?: boolean
}) => {
  const oldTags = tagsOld && Object.keys(tagsOld).length > 0 ? tagsOld : null
  const rows = computeDiffRows(tags, oldTags, diff)
  if (!rows.length) return null

  return (
    <div class="tags">
      <table class="table table-sm">
        <tbody dir="auto">
          {rows.map((row) => (
            <TagRow
              key={row.key}
              tagKey={row.key}
              value={row.value}
              oldValue={row.oldValue}
              status={row.status}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
