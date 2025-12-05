import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"

mount("admin-tasks-body", (body) => {
    const updateStatus = async () => {
        try {
            const resp = await fetch("/api/web/admin/tasks/status")
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
            const data: Array<{ id: string; running: boolean }> = await resp.json()
            const infoMap = new Map(data.map((item) => [item.id, item]))
            console.debug("Updating tasks status", data)

            for (const form of forms) {
                const taskId = form.querySelector("input[name=id]")
                const taskInfo = infoMap.get(taskId.value)
                if (!taskInfo) {
                    console.warn("Task not found", taskId.value)
                    continue
                }

                const badge = form.closest(".card").querySelector(".status-badge")
                badge.textContent = taskInfo.running ? "Running" : "Idle"
                badge.classList.toggle("bg-success", taskInfo.running)
                badge.classList.toggle("bg-secondary", !taskInfo.running)
            }
        } catch (error) {
            if (error.name === "AbortError") return
            console.error("Failed to fetch tasks status", error)
        }
    }

    const forms = body.querySelectorAll("form.task-form")
    if (forms.length) {
        for (const form of forms) {
            configureStandardForm(
                form,
                () => {
                    updateStatus()
                },
                { removeEmptyFields: true },
            )
        }

        updateStatus()
        setInterval(updateStatus, 20_000)
    }
})
