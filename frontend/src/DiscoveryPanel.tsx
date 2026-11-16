import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  apiRequest,
  type DiscoverySchedule,
  type DiscoveryScheduleList,
  type DiscoverySource,
  type DiscoveryTask,
  type DiscoveryTaskEnqueueResponse,
  type DiscoveryTaskListResponse,
  type OperationsSummary,
} from "./api";

type Props = {
  onJobsRefresh: () => Promise<void>;
};

const CADENCES = [
  { label: "Every hour", seconds: 3600 },
  { label: "Every 6 hours", seconds: 21_600 },
  { label: "Every 12 hours", seconds: 43_200 },
  { label: "Daily", seconds: 86_400 },
  { label: "Weekly", seconds: 604_800 },
];

function DiscoveryPanel({ onJobsRefresh }: Props) {
  const [sources, setSources] = useState<DiscoverySource[]>([]);
  const [tasks, setTasks] = useState<DiscoveryTask[]>([]);
  const [schedules, setSchedules] = useState<DiscoverySchedule[]>([]);
  const [operations, setOperations] = useState<OperationsSummary | null>(null);
  const [selectedSourceKeys, setSelectedSourceKeys] = useState<string[]>([]);
  const [sourceSelectionInitialized, setSourceSelectionInitialized] = useState(false);
  const [scheduleName, setScheduleName] = useState("Daily public job refresh");
  const [scheduleInterval, setScheduleInterval] = useState(86_400);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refreshData() {
    setBusy("refresh");
    setError("");
    try {
      const [sourceResponse, taskResponse, scheduleResponse, operationsResponse] = await Promise.all([
        apiRequest<{ items: DiscoverySource[] }>("/discovery/sources"),
        apiRequest<DiscoveryTaskListResponse>("/discovery/tasks?limit=30"),
        apiRequest<DiscoveryScheduleList>("/discovery/schedules"),
        apiRequest<OperationsSummary>("/operations/summary"),
      ]);
      setSources(sourceResponse.items);
      setTasks(taskResponse.items);
      setSchedules(scheduleResponse.items);
      setOperations(operationsResponse);
      setSelectedSourceKeys((current) => {
        const available = sourceResponse.items.map((source) => source.source_key);
        return sourceSelectionInitialized
          ? current.filter((key) => available.includes(key))
          : available;
      });
      setSourceSelectionInitialized(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not load discovery sources, tasks, and schedules.",
      );
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  function toggleSource(sourceKey: string) {
    setSelectedSourceKeys((current) =>
      current.includes(sourceKey)
        ? current.filter((key) => key !== sourceKey)
        : [...current, sourceKey],
    );
  }

  async function startDiscovery() {
    if (selectedSourceKeys.length === 0) return;
    setBusy("enqueue");
    setError("");
    setNotice("");
    try {
      const created = await apiRequest<DiscoveryTaskEnqueueResponse>("/discovery/tasks", {
        method: "POST",
        body: JSON.stringify({
          source_keys: selectedSourceKeys,
          idempotency_key: "workspace-" + crypto.randomUUID(),
        }),
      });
      setTasks((current) => [
        ...created.items,
        ...current.filter((task) => !created.items.some((item) => item.id === task.id)),
      ].slice(0, 30));
      setNotice(
        "Queued " + created.items.length + " source refresh task(s). "
        + "Start the local worker to execute them.",
      );
      await refreshData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not queue source discovery.");
    } finally {
      setBusy(null);
    }
  }

  async function createSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedSourceKeys.length === 0) return;
    setBusy("schedule-create");
    setError("");
    setNotice("");
    try {
      const created = await apiRequest<DiscoverySchedule>("/discovery/schedules", {
        method: "POST",
        body: JSON.stringify({
          name: scheduleName,
          source_keys: selectedSourceKeys,
          interval_seconds: scheduleInterval,
        }),
      });
      setSchedules((current) => [created, ...current]);
      setNotice("Schedule saved. Its first discovery run is due immediately when the local scheduler is running.");
      await refreshData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create discovery schedule.");
    } finally {
      setBusy(null);
    }
  }

  async function toggleSchedule(schedule: DiscoverySchedule) {
    setBusy("schedule:" + schedule.id);
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<DiscoverySchedule>(
        "/discovery/schedules/" + encodeURIComponent(schedule.id),
        {
          method: "PATCH",
          body: JSON.stringify({ is_enabled: !schedule.is_enabled }),
        },
      );
      setSchedules((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(updated.is_enabled ? "Discovery schedule resumed." : "Discovery schedule paused.");
      await refreshData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update discovery schedule.");
    } finally {
      setBusy(null);
    }
  }

  async function deleteSchedule(scheduleId: string) {
    setBusy("delete-schedule:" + scheduleId);
    setError("");
    setNotice("");
    try {
      await apiRequest<void>("/discovery/schedules/" + encodeURIComponent(scheduleId), {
        method: "DELETE",
      });
      setSchedules((current) => current.filter((item) => item.id !== scheduleId));
      setNotice("Schedule deleted. Already queued discovery tasks remain in the worker queue.");
      await refreshData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete discovery schedule.");
    } finally {
      setBusy(null);
    }
  }

  async function cancelTask(taskId: string) {
    setBusy("cancel:" + taskId);
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<DiscoveryTask>(
        "/discovery/tasks/" + encodeURIComponent(taskId) + "/cancel",
        { method: "POST" },
      );
      setTasks((current) => current.map((task) => task.id === updated.id ? updated : task));
      setNotice("Discovery task cancelled.");
      await refreshData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not cancel discovery task.");
    } finally {
      setBusy(null);
    }
  }

  async function refreshJobs() {
    setBusy("jobs");
    setError("");
    setNotice("");
    try {
      await onJobsRefresh();
      setNotice("Indexed job results refreshed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not refresh indexed jobs.");
    } finally {
      setBusy(null);
    }
  }

  function sourceNames(sourceKeys: string[]): string {
    return sourceKeys.map((key) =>
      sources.find((source) => source.source_key === key)?.company_name ?? key,
    ).join(", ");
  }

  function cadenceLabel(seconds: number): string {
    return CADENCES.find((cadence) => cadence.seconds === seconds)?.label
      ?? Math.round(seconds / 3600) + " hours";
  }

  const queuedCount = (operations?.task_counts.queued ?? 0)
    + (operations?.task_counts.retry_wait ?? 0);
  const runningCount = operations?.task_counts.running ?? 0;
  const failedCount = (operations?.task_counts.failed ?? 0)
    + (operations?.task_counts.needs_attention ?? 0);

  return (
    <section className="panel discovery-panel">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">04 / BACKGROUND DISCOVERY</p>
          <h2>Refresh public job sources</h2>
        </div>
        <span className="result-count">{tasks.length} recent tasks</span>
      </div>
      {operations && (
        <div className="operations-summary" aria-label="Local operations summary">
          <div className="application-metadata">
            <span>Database: {operations.database_status}</span>
            <span>{operations.configured_source_count} configured sources</span>
            <span>{operations.enabled_schedule_count} active schedules</span>
            <span>{operations.due_schedule_count} schedules due</span>
          </div>
          <div className="application-metadata">
            <span>{queuedCount} queued/retrying tasks</span>
            <span>{runningCount} running tasks</span>
            <span>{failedCount} failed/attention tasks</span>
            {operations.expired_lease_count > 0 && (
              <span className="workflow-warning">
                {operations.expired_lease_count} expired task lease(s) need worker recovery
              </span>
            )}
          </div>
          <p className="workflow-muted">
            Summary updated {new Date(operations.generated_at).toLocaleTimeString()}.
            The API can verify database access; it does not claim that the separate worker or scheduler process is running.
          </p>
        </div>
      )}
      <p className="workflow-muted">
        Discovery runs in a separate local worker. Configure public Greenhouse or Lever board
        identifiers in your environment, then keep the worker running while tasks execute.
      </p>

      {(error || notice) && (
        <div className={error ? "feedback feedback-error" : "feedback feedback-success"} role="status">
          <span>{error || notice}</span>
          <button type="button" className="feedback-close" onClick={() => { setError(""); setNotice(""); }}>
            Dismiss
          </button>
        </div>
      )}

      {sources.length ? (
        <div className="discovery-source-list">
          {sources.map((source) => (
            <label className="check-row discovery-source-row" key={source.source_key}>
              <input
                type="checkbox"
                checked={selectedSourceKeys.includes(source.source_key)}
                onChange={() => toggleSource(source.source_key)}
              />
              <span>
                <strong>{source.company_name}</strong>
                <small>{source.provider} · {source.source_key}</small>
              </span>
            </label>
          ))}
        </div>
      ) : (
        <div className="empty-state discovery-empty">
          <strong>No public job boards configured.</strong>
          <span>
            Set VACANCYX_GREENHOUSE_BOARDS or VACANCYX_LEVER_SITES in .env and restart the API
            and worker. Only official public board identifiers are accepted.
          </span>
        </div>
      )}

      <div className="workflow-actions discovery-actions">
        <button
          className="button button-primary"
          type="button"
          disabled={!selectedSourceKeys.length || busy === "enqueue"}
          onClick={() => void startDiscovery()}
        >
          {busy === "enqueue" ? "Queueing…" : "Queue selected sources"}
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={busy === "refresh"}
          onClick={() => void refreshData()}
        >
          {busy === "refresh" ? "Refreshing…" : "Refresh task statuses"}
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={busy === "jobs"}
          onClick={() => void refreshJobs()}
        >
          {busy === "jobs" ? "Loading jobs…" : "Refresh indexed jobs"}
        </button>
      </div>

      <form className="schedule-create-form" onSubmit={(event) => void createSchedule(event)}>
        <div className="workflow-section-heading">
          <h3>Recurring discovery</h3>
          <span>{schedules.length} saved</span>
        </div>
        <p className="workflow-muted">
          Schedule the selected sources to refresh automatically. The first run is due immediately;
          later runs follow your chosen cadence.
        </p>
        <div className="schedule-create-fields">
          <label className="field">
            <span>Schedule name</span>
            <input
              value={scheduleName}
              onChange={(event) => setScheduleName(event.target.value)}
              required
              maxLength={120}
            />
          </label>
          <label className="field">
            <span>Run frequency</span>
            <select
              value={scheduleInterval}
              onChange={(event) => setScheduleInterval(Number(event.target.value))}
            >
              {CADENCES.map((cadence) => (
                <option key={cadence.seconds} value={cadence.seconds}>{cadence.label}</option>
              ))}
            </select>
          </label>
        </div>
        <button
          className="button button-secondary"
          type="submit"
          disabled={!selectedSourceKeys.length || busy === "schedule-create"}
        >
          {busy === "schedule-create" ? "Saving schedule…" : "Save recurring schedule"}
        </button>
      </form>

      <div className="schedule-list">
        <div className="workflow-section-heading">
          <h3>Saved schedules</h3>
          <span>{schedules.length}</span>
        </div>
        {schedules.map((schedule) => (
          <article className="schedule-item" key={schedule.id}>
            <div className="workflow-item-heading">
              <div>
                <strong>{schedule.name}</strong>
                <span>{sourceNames(schedule.source_keys)} · {cadenceLabel(schedule.interval_seconds)}</span>
              </div>
              <span className={schedule.is_enabled ? "status-pill status-active" : "status-pill"}>
                {schedule.is_enabled ? "Enabled" : "Paused"}
              </span>
            </div>
            <div className="application-metadata">
              <span>Run #{schedule.run_number}</span>
              <span>Next: {new Date(schedule.next_run_at).toLocaleString()}</span>
              {schedule.last_run_at && <span>Last: {new Date(schedule.last_run_at).toLocaleString()}</span>}
            </div>
            {schedule.last_error_code && (
              <p className="workflow-warning">{schedule.last_error_code}: check configured public source identifiers.</p>
            )}
            <div className="workflow-actions schedule-actions">
              <button
                className="text-button"
                type="button"
                disabled={busy === "schedule:" + schedule.id}
                onClick={() => void toggleSchedule(schedule)}
              >
                {busy === "schedule:" + schedule.id
                  ? "Saving…"
                  : schedule.is_enabled ? "Pause" : "Resume"}
              </button>
              <button
                className="text-button text-button-danger"
                type="button"
                disabled={busy === "delete-schedule:" + schedule.id}
                onClick={() => void deleteSchedule(schedule.id)}
              >
                {busy === "delete-schedule:" + schedule.id ? "Deleting…" : "Delete"}
              </button>
            </div>
          </article>
        ))}
        {schedules.length === 0 && (
          <p className="workflow-muted">No recurring schedules yet. Select one or more sources and save a schedule above.</p>
        )}
      </div>

      <div className="worker-command">
        <span>Run in separate terminals on this machine</span>
        <code>vacancyx-scheduler</code>
        <code>vacancyx-worker</code>
      </div>

      <div className="discovery-task-list">
        <div className="workflow-section-heading">
          <h3>Recent discovery tasks</h3>
          <span>{tasks.length}</span>
        </div>
        {tasks.map((task) => (
          <article className="discovery-task-item" key={task.id}>
            <div className="workflow-item-heading">
              <div>
                <strong>{task.source_key ?? task.result?.source_key ?? task.task_type}</strong>
                <span>Updated {new Date(task.updated_at).toLocaleString()}</span>
              </div>
              <span className="status-pill">{task.state.replaceAll("_", " ")}</span>
            </div>
            <div className="application-metadata">
              <span>Attempt {task.attempts}/{task.max_attempts}</span>
              {task.result && <span>{task.result.jobs_created ?? 0} jobs added</span>}
              {task.result && <span>{task.result.pages_fetched ?? 0} pages fetched</span>}
              {task.result?.truncated && <span className="workflow-warning">Page limit reached</span>}
            </div>
            {task.last_error_message && (
              <p className="workflow-warning">
                {task.last_error_code}: {task.last_error_message}
              </p>
            )}
            {["queued", "retry_wait", "running"].includes(task.state) && (
              <button
                className="text-button"
                type="button"
                disabled={busy === "cancel:" + task.id}
                onClick={() => void cancelTask(task.id)}
              >
                {busy === "cancel:" + task.id ? "Cancelling…" : "Cancel task"}
              </button>
            )}
          </article>
        ))}
        {tasks.length === 0 && (
          <p className="workflow-muted">No discovery tasks yet. Queue a configured source to begin.</p>
        )}
      </div>
    </section>
  );
}

export default DiscoveryPanel;
