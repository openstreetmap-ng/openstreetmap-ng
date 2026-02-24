import {
  PageSchema,
  Service,
  type ListResponse,
  type ListResponse_TaskValid,
} from "@lib/proto/admin_tasks_pb"
import { mountProtoPage } from "@lib/proto-page"
import { rpcUnary } from "@lib/rpc"
import { StandardForm } from "@lib/standard-form"
import { useSignal } from "@preact/signals"
import { SECOND } from "@std/datetime/constants"
import { useEffect } from "preact/hooks"
import { SettingsNav } from "../settings/_nav"

const AdminTaskCard = ({
  task,
  onSuccess,
}: {
  task: ListResponse_TaskValid
  onSuccess: () => void
}) => (
  <div class="card mb-4">
    <h5 class="card-header mb-0">
      <code>{task.id}</code>
    </h5>
    <div class="card-body">
      <StandardForm
        method={Service.method.start}
        buildRequest={({ formData }) => ({
          taskId: task.id,
          arguments: Object.fromEntries(
            [...formData.entries()]
              .filter(
                ([key, value]) =>
                  key.startsWith("arg_") &&
                  typeof value === "string" &&
                  value.length > 0,
              )
              .map(([key, value]) => [key.slice(4), value]),
          ),
        })}
        onSuccess={onSuccess}
      >
        {task.arguments.map((arg) => (
          <div
            key={arg.name}
            class="mb-3"
          >
            <label class="form-label d-block">
              <span class={arg.required ? "required" : ""}>{arg.name}</span>
              <input
                type={arg.numeric ? "number" : "text"}
                class="form-control mt-2"
                name={`arg_${arg.name}`}
                placeholder={arg.default}
                autoCapitalize="none"
                required={arg.required}
              />
            </label>
            <div class="form-text">Type: {arg.type}</div>
          </div>
        ))}

        <div class="d-flex justify-content-between align-items-end">
          <button
            type="submit"
            class="btn btn-primary"
          >
            Start task
          </button>
          <span class={`badge ${task.running ? "bg-success" : "bg-secondary"}`}>
            {task.running ? "Running" : "Idle"}
          </span>
        </div>
      </StandardForm>
    </div>
  </div>
)

mountProtoPage(PageSchema, () => {
  const tasks = useSignal<ListResponse["tasks"]>([])
  const refresh = async () => {
    const resp = await rpcUnary(Service.method.list)({})
    tasks.value = resp.tasks
  }

  useEffect(() => {
    void refresh()
    const interval = setInterval(() => {
      void refresh()
    }, 20 * SECOND)
    return () => clearInterval(interval)
  }, [])

  return (
    <>
      <div class="content-header">
        <h1 class="container">Administrative tasks</h1>
      </div>

      <div class="content-body">
        <div class="container">
          <div class="row">
            <div class="col-lg-auto mb-4">
              <SettingsNav />
            </div>

            <div class="col-lg">
              <div class="row">
                {tasks.value.map((task) => (
                  <div
                    key={task.id}
                    class="col-xl-6"
                  >
                    <AdminTaskCard
                      task={task}
                      onSuccess={refresh}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
})
