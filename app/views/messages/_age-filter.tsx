import { t } from "i18next"
import { olderThan } from "./_age"

export const AgeFilter = ({
  busy,
  onApply,
}: {
  busy: boolean
  onApply: (cutoff: bigint) => void
}) => (
  <form
    class="row g-2 mb-3"
    onSubmit={(event) => {
      event.preventDefault()
      const data = new FormData(event.currentTarget)
      onApply(olderThan(Number(data.get("age_count")), String(data.get("age_unit"))))
    }}
  >
    <fieldset
      class="border rounded p-3"
      disabled={busy}
    >
      <legend class="float-none w-auto fs-6 px-1">
        {t("mailbox_tools.older_than")}
      </legend>
      <div class="d-flex flex-wrap gap-2 align-items-end">
        <label>
          <span class="form-label">{t("mailbox_tools.age_count")}</span>
          <input
            class="form-control"
            name="age_count"
            type="number"
            min="1"
            max="100"
            step="1"
            required
            defaultValue="3"
          />
        </label>
        <label>
          <span class="form-label">{t("mailbox_tools.age_unit")}</span>
          <select
            class="form-select"
            name="age_unit"
            defaultValue="weeks"
          >
            <option value="days">{t("mailbox_tools.age_days")}</option>
            <option value="weeks">{t("mailbox_tools.age_weeks")}</option>
            <option value="months">{t("mailbox_tools.age_months")}</option>
            <option value="years">{t("mailbox_tools.age_years")}</option>
          </select>
        </label>
        <button
          type="submit"
          class="btn btn-secondary"
        >
          {t("mailbox_tools.review_old")}
        </button>
      </div>
      <p class="small text-muted mb-0 mt-2">{t("mailbox_tools.review_old_help")}</p>
    </fieldset>
  </form>
)
