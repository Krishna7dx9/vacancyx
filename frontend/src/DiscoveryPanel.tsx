import { useEffect, useState } from "react";

import {
  apiRequest,
  type DiscoverySource,
  type DiscoveryTask,
  type DiscoveryTaskEnqueueResponse,
  type DiscoveryTaskListResponse,
} from "./api";

type Props = {
  onJobsRefresh: () => Promise<void>;
};

function DiscoveryPanel({ onJobsRefresh }: Props) {
  const [sources, setSources] = useState<DiscoverySource[]>([]);
  const [tasks, setTasks] = useState<DiscoveryTask[]>([]);
  const [selectedSourceKeys, setSelectedSourceKeys] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refreshData() {
    setBusy("refresh");
    setError("");
    try {
      const [sourceResponse, taskResponse] = await Promise.all([
        apiRequest<{ items: DiscoverySource[] }>("/discovery/sources"),
        apiRequest<DiscoveryTaskListResponse>("/discovery/tasks?limit=30"),
      ]);
      setSources(sourceResponse.items);
      setTasks(taskResponse.items);
      setSelectedSourceKeys((current) => {
        const available = sourceResponse.items.map((source) => source.source_key);
        return current.length
          ? current.filter((key) => available.includes(key))
          : available;
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load discovery sources and tasks.");
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
      setNotice("Queued " + created.items.length + " source refresh task(s). Start the local worker to execute them.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not queue source discovery.");
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

  return (
    <section className="panel discovery-panel">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">04 / BACKGROUND DISCOVERY</p>
          <h2>Refresh public job sources</h2>
        </div>
        <span className="result-count">{tasks.length} recent tasks</span>
      </div>
      <p className="workflow-muted">
        Discovery runs in a separate local worker. Configure public Greenhouse or Lever board identifiers in your environment, then keep the worker running while tasks execute.
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
            Set VACANCYX_GREENHOUSE_BOARDS or VACANCYX_LEVER_SITES in .env and restart the API and worker. Only official public board identifiers are accepted.
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

      <div className="worker-command">
        <span>Run in a separate terminal</span>
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
