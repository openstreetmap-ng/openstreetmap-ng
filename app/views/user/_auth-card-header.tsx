import { t } from "i18next"
import type { ComponentChildren } from "preact"

export const AuthCardHeader = ({
  eyebrow,
  title,
  titleId,
  subtitle,
  children,
  class: className = "",
  headingLevel = 4,
  subtitleClass = "form-text mt-0",
  titleClass = "modal-title",
  showLogo = true,
}: {
  eyebrow?: ComponentChildren
  title: ComponentChildren
  titleId?: string | undefined
  subtitle?: ComponentChildren
  children?: ComponentChildren
  class?: string
  headingLevel?: 1 | 4
  subtitleClass?: string
  titleClass?: string
  showLogo?: boolean
}) => (
  <div class={`auth-card-header text-center mb-4 ${className}`}>
    {showLogo && (
      <img
        class="auth-card-logo mb-2"
        src="/static/img/favicon/256.webp"
        alt={t("alt.logo", { name: t("project_name") })}
      />
    )}
    {eyebrow && (
      <p class="text-body-secondary text-uppercase small fw-semibold mb-1">{eyebrow}</p>
    )}
    {headingLevel === 1 ? (
      <h1
        id={titleId}
        class={titleClass}
      >
        {title}
      </h1>
    ) : (
      <h4
        id={titleId}
        class={titleClass}
      >
        {title}
      </h4>
    )}
    {subtitle && <p class={subtitleClass}>{subtitle}</p>}
    {children}
  </div>
)
