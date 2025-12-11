import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { assert } from "@std/assert"
import { SECOND } from "@std/datetime/constants"

mount("admin-tasks-body", (body) => {
    const updateStatus = async () => {
        const resp = await fetch("/api/web/admin/tasks/status")
        assert(resp.ok, `${resp.status} ${resp.statusText}`)
        const data: Array<{ id: string; running: boolean }> = await resp.json()
        const infoMap = new Map(data.map((item) => [item.id, item]))
        console.debug("AdminTasks: Updating status", data)

        for (const form of forms) {
            const taskId = form.querySelector("input[name=id]")!
            const taskInfo = infoMap.get(taskId.value)
            if (!taskInfo) {
                console.warn("AdminTasks: Task not found", taskId.value)
                continue
            }

            const badge = form.closest(".card")!.querySelector(".status-badge")!
            badge.textContent = taskInfo.running ? "Running" : "Idle"
            badge.classList.toggle("bg-success", taskInfo.running)
            badge.classList.toggle("bg-secondary", !taskInfo.running)
        }
    }

    const forms = body.querySelectorAll("form.task-form")
    if (forms.length) {
        for (const form of forms) {
            configureStandardForm(form, updateStatus, { removeEmptyFields: true })
        }

        updateStatus()
        setInterval(updateStatus, 20 * SECOND)
    }
})
