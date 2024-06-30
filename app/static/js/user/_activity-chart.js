import { Tooltip } from "bootstrap"

const table = document.getElementById("activity-table")

const multiple = "{num} activities on {date}"
const single = "1 activitiy on {date}"
const none = "No activities on {date}"



if (table) {
    table.querySelectorAll('td[class*="activity"]').forEach(element => {
        const [amount,date] = [+element.dataset.total, element.dataset.date]
        const text = amount === 0 ? none : (amount === 1 ? single : multiple.replace("{num}", amount))
        Tooltip.getOrCreateInstance(element, {
            title: text.replace("{date}", date),
            placement: "bottom"
        })
    })
}
