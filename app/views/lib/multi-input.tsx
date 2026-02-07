import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { render } from "preact"
import { useRef } from "preact/hooks"

const MULTI_INPUT_DELIMITER = ","

const normalizeMultiInputToken = (value: string, maxItemLength?: number) => {
  const trimmed = value.trim()
  if (!trimmed) return null
  return maxItemLength ? trimmed.slice(0, maxItemLength) : trimmed
}

const insertToken = (
  current: string[],
  token: string,
  maxItems: number | undefined,
): readonly [next: string[], blocked: boolean] => {
  const index = current.indexOf(token)
  if (index === -1) {
    if (maxItems !== undefined && current.length >= maxItems) {
      return [current, true]
    }
    return [[...current, token], false]
  }
  if (index === current.length - 1) return [current, false]
  return [[...current.slice(0, index), ...current.slice(index + 1), token], false]
}

const seedTokens = (
  raw: string,
  maxItems: number | undefined,
  maxItemLength?: number,
) => {
  let tokens: string[] = []
  for (const value of raw.split(MULTI_INPUT_DELIMITER)) {
    const normalized = normalizeMultiInputToken(value, maxItemLength)
    if (!normalized) continue
    const [next] = insertToken(tokens, normalized, maxItems)
    tokens = next
  }
  return tokens
}

export const MultiInput = ({
  name,
  id = `multi-input-${name}`,
  defaultValue = "",
  placeholder = "",
  required = false,
  maxItems,
  maxItemLength,
}: {
  name: string
  id?: string | undefined
  defaultValue?: string | undefined
  placeholder?: string | undefined
  required?: boolean | undefined
  maxItems?: readonly [limit: number, message: string] | undefined
  maxItemLength?: number | undefined
}) => {
  const maxItemsLimit = maxItems?.[0]
  const maxItemsFeedback = maxItems?.[1]

  const tokens = useSignal<string[]>(
    seedTokens(defaultValue, maxItemsLimit, maxItemLength),
  )
  const latestInsertBlocked = useSignal(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const getInputValue = () => inputRef.current?.value ?? ""

  const setInputValue = (value: string) => {
    const input = inputRef.current
    if (input) input.value = value
  }

  const setInputCursorEnd = () => {
    const input = inputRef.current
    if (!input) return
    const len = input.value.length
    input.setSelectionRange(len, len)
  }

  const tryInsert = (raw: string) => {
    const normalized = normalizeMultiInputToken(raw, maxItemLength)
    if (!normalized) {
      latestInsertBlocked.value = false
      return "empty" as const
    }
    const current = tokens.peek()
    const [next, blocked] = insertToken(current, normalized, maxItemsLimit)
    if (!blocked && next !== current) tokens.value = next
    latestInsertBlocked.value = blocked
    return blocked ? ("blocked" as const) : ("accepted" as const)
  }

  const commitInput = () => {
    if (tryInsert(getInputValue()) !== "blocked") setInputValue("")
  }

  const editLastToken = () => {
    const current = tokens.peek()
    const value = current.at(-1)
    if (!value) return

    tokens.value = current.slice(0, -1)
    setInputValue(value)
    inputRef.current?.focus()
    setInputCursorEnd()
  }

  const removeTokenValue = (value: string) => {
    const current = tokens.peek()
    const index = current.indexOf(value)
    if (index === -1) return
    tokens.value = [...current.slice(0, index), ...current.slice(index + 1)]
  }

  const editToken = (value: string) => {
    commitInput()
    removeTokenValue(value)
    setInputValue(value)
    inputRef.current?.focus()
    setInputCursorEnd()
  }

  const visibleTokens = tokens.value
  const showLimitFeedback =
    latestInsertBlocked.value &&
    maxItemsLimit !== undefined &&
    visibleTokens.length >= maxItemsLimit

  return (
    <div class="multi-input-container">
      <div class="form-control d-flex flex-wrap align-items-center">
        <div class="multi-input-tokens d-flex flex-wrap align-items-center gap-1">
          {visibleTokens.map((value) => (
            <span
              key={value}
              class="multi-input-token d-inline-flex align-items-center"
            >
              <button
                type="button"
                class="multi-input-label"
                onClick={() => editToken(value)}
              >
                {value}
              </button>
              <button
                type="button"
                class="multi-input-remove"
                aria-label={t("action.remove")}
                onClick={(event) => {
                  event.stopPropagation()
                  removeTokenValue(value)
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>

        <input
          id={id}
          ref={inputRef}
          type="text"
          class="form-control"
          placeholder={visibleTokens.length ? "" : placeholder}
          maxLength={maxItemLength}
          required={required && !visibleTokens.length}
          autoComplete="off"
          autoCapitalize="none"
          enterKeyHint="enter"
          onInput={(event) => {
            const raw = event.currentTarget.value
            if (!raw.includes(MULTI_INPUT_DELIMITER)) {
              if (latestInsertBlocked.peek()) latestInsertBlocked.value = false
              return
            }

            const parts = raw.split(MULTI_INPUT_DELIMITER)
            for (const token of parts.slice(0, -1)) {
              if (tryInsert(token) !== "blocked") continue
              break
            }
            event.currentTarget.value =
              normalizeMultiInputToken(parts.at(-1)!, maxItemLength) ?? ""
          }}
          onKeyDown={(event) => {
            if (event.isComposing) return
            if (event.key === "Enter" || event.key === MULTI_INPUT_DELIMITER) {
              event.preventDefault()
              commitInput()
            } else if (event.key === "Backspace" && !event.currentTarget.value) {
              event.preventDefault()
              editLastToken()
            }
          }}
          onBlur={commitInput}
        />
      </div>

      {visibleTokens.map((value) => (
        <input
          key={`hidden-${value}`}
          type="hidden"
          name={name}
          value={value}
        />
      ))}

      {showLimitFeedback ? (
        <div class="form-text text-danger">{maxItemsFeedback!}</div>
      ) : (
        <div class="form-text">
          {t("multi_input.add_new_entries_with_enter_or_comma")}{" "}
          {t("multi_input.use_backspace_to_edit_the_last_item")}
        </div>
      )}
    </div>
  )
}

const roots = document.querySelectorAll<HTMLElement>(
  ".multi-input-container[data-name]",
)
console.debug("MultiInput: Initializing", roots.length)
for (const root of roots) {
  const {
    name,
    id,
    placeholder,
    value,
    required,
    maxItems,
    maxItemsError,
    maxItemLength,
  } = root.dataset

  render(
    <MultiInput
      name={name!}
      id={id}
      placeholder={placeholder}
      defaultValue={value}
      required={Boolean(required)}
      maxItems={
        maxItems
          ? ([Number.parseInt(maxItems, 10), maxItemsError!] as const)
          : undefined
      }
      maxItemLength={maxItemLength ? Number.parseInt(maxItemLength, 10) : undefined}
    />,
    root,
  )
}
