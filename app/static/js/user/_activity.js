import { Tooltip } from "bootstrap"
import i18next from "i18next"

const table = document.getElementById("activity-table")

if (table) {
    const multiple = i18next.t("user.activity.multiple")
    const single = i18next.t("user.activity.single")
    const none = i18next.t("user.activity.none")

    // add tooltips
    table.querySelectorAll(".activity").forEach((element) => {
        const [amount, date] = [+element.dataset.total, element.dataset.date]
        const text = amount === 0 ? none : amount === 1 ? single : multiple.replace("{{count}}", amount)
        Tooltip.getOrCreateInstance(element, {
            title: text.replace("{{date}}", date),
            placement: "bottom",
        })
    })
}
