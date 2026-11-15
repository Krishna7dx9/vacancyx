import { useState } from "react";

import {
  apiRequest,
  type Application,
  type ApplicationStatusRead,
  type ApplicationTimelineEvent,
  type ApplicationTimelineEventType,
} from "./api";

type Props = {
  candidateId: string;
  applications: Application[];
  onApplicationUpdated: (updated: ApplicationStatusRead) => void;
};

type StatusAction = {
  status: string;
  label: string;
  requiresConfirmation?: boolean;
};

type EventDraft = {
  eventType: ApplicationTimelineEventType;
  summary: string;
};

const STATUS_ACTIONS: Record<string, StatusAction[]> = {
  prepared: [{ status: "withdrawn", label: "Withdraw application" }],
  draft: [{ status: "withdrawn", label: "Withdraw application" }],
  approved: [
    { status: "submitting", label: "Mark submission started" },
    { status: "blocked", label: "Mark blocked" },
    { status: "withdrawn", label: "Withdraw application" },
  ],
  submitting: [
    { status: "submitted", label: "Record confirmed submission", requiresConfirmation: true },
    { status: "uncertain", label: "Mark outcome uncertain" },
    { status: "blocked", label: "Mark blocked" },
  ],
  uncertain: [
    { status: "submitted", label: "Confirm submitted", requiresConfirmation: true },
    { status: "blocked", label: "Mark blocked" },
    { status: "withdrawn", label: "Withdraw application" },
  ],
  submitted: [
    { status: "rejected", label: "Mark rejected" },
    { status: "withdrawn", label: "Withdraw application" },
  ],
  blocked: [{ status: "withdrawn", label: "Withdraw application" }],
};

const EVENT_OPTIONS: Array<{ value: ApplicationTimelineEventType; label: string }> = [
  { value: "note", label: "Note" },
  { value: "assessment_scheduled", label: "Assessment scheduled" },
  { value: "assessment_completed", label: "Assessment completed" },
  { value: "interview_scheduled", label: "Interview scheduled" },
  { value: "interview_completed", label: "Interview completed" },
  { value: "offer_received", label: "Offer received" },
  { value: "offer_declined", label: "Offer declined" },
  { value: "follow_up", label: "Follow-up" },
];

function candidateApplicationPath(candidateId: string, applicationId: string, suffix: string): string {
  return "/candidates/" + encodeURIComponent(candidateId) +
    "/applications/" + encodeURIComponent(applicationId) + suffix;
}

function eventSummary(event: ApplicationTimelineEvent): string {
  const metadata = event.metadata_json;
  if (typeof metadata.summary === "string") return metadata.summary;
  if (event.event_type === "status_changed") {
    return String(metadata.from_status ?? "Unknown") + " → " +
      String(metadata.to_status ?? "Unknown");
  }
  return "Timeline event recorded.";
}

function ApplicationTrackingPanel({
  candidateId,
  applications,
  onApplicationUpdated,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [eventsByApplication, setEventsByApplication] = useState<
    Record<string, ApplicationTimelineEvent[]>
  >({});
  const [loadedApplicationIds, setLoadedApplicationIds] = useState<string[]>([]);
  const [confirmationRefs, setConfirmationRefs] = useState<Record<string, string>>({});
  const [eventDrafts, setEventDrafts] = useState<Record<string, EventDraft>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadTimeline(applicationId: string) {
    if (loadedApplicationIds.includes(applicationId)) return;
    setBusy("timeline:" + applicationId);
    setError("");
    try {
      const events = await apiRequest<ApplicationTimelineEvent[]>(
        candidateApplicationPath(candidateId, applicationId, "/events"),
      );
      setEventsByApplication((current) => ({ ...current, [applicationId]: events }));
      setLoadedApplicationIds((current) => [...current, applicationId]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load the application timeline.");
    } finally {
      setBusy(null);
    }
  }

  async function toggleTimeline(applicationId: string) {
    if (expandedId === applicationId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(applicationId);
    await loadTimeline(applicationId);
  }

  async function transition(application: Application, action: StatusAction) {
    const confirmationReference = confirmationRefs[application.id]?.trim() ?? "";
    if (action.requiresConfirmation && !confirmationReference) {
      setError("Enter the employer portal confirmation reference before recording submission.");
      return;
    }
    setBusy("status:" + application.id);
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<ApplicationStatusRead>(
        candidateApplicationPath(candidateId, application.id, "/status"),
        {
          method: "PATCH",
          body: JSON.stringify({
            status: action.status,
            ...(action.requiresConfirmation
              ? { confirmation_reference: confirmationReference }
              : {}),
          }),
        },
      );
      onApplicationUpdated(updated);
      setNotice("Application status updated to " + updated.status + ".");
      if (loadedApplicationIds.includes(application.id)) {
        const events = await apiRequest<ApplicationTimelineEvent[]>(
          candidateApplicationPath(candidateId, application.id, "/events"),
        );
        setEventsByApplication((current) => ({ ...current, [application.id]: events }));
      }
      if (action.status === "submitted") {
        setConfirmationRefs((current) => ({ ...current, [application.id]: "" }));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update application status.");
    } finally {
      setBusy(null);
    }
  }

  async function addTimelineEvent(applicationId: string) {
    const draft = eventDrafts[applicationId] ?? { eventType: "note", summary: "" };
    if (!draft.summary.trim()) {
      setError("Enter a short timeline note first.");
      return;
    }
    setBusy("event:" + applicationId);
    setError("");
    setNotice("");
    try {
      const created = await apiRequest<ApplicationTimelineEvent>(
        candidateApplicationPath(candidateId, applicationId, "/events"),
        {
          method: "POST",
          body: JSON.stringify({
            event_type: draft.eventType,
            summary: draft.summary.trim(),
          }),
        },
      );
      setEventsByApplication((current) => ({
        ...current,
        [applicationId]: [...(current[applicationId] ?? []), created],
      }));
      setEventDrafts((current) => ({
        ...current,
        [applicationId]: { ...draft, summary: "" },
      }));
      setNotice("Timeline event saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save timeline event.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="workflow-subpanel tracking-panel">
      <div className="workflow-section-heading">
        <h3>Application lifecycle and timeline</h3>
        <span>{applications.length} applications</span>
      </div>
      <p className="workflow-muted">
        Record real submission progress and interview activity. VacancyX does not submit to employer portals in this workflow.
      </p>

      {(error || notice) && (
        <div className={error ? "feedback feedback-error" : "feedback feedback-success"} role="status">
          <span>{error || notice}</span>
          <button type="button" className="feedback-close" onClick={() => { setError(""); setNotice(""); }}>
            Dismiss
          </button>
        </div>
      )}

      {applications.length ? (
        <div className="workflow-list">
          {applications.map((application) => {
            const snapshot = application.latest_revision?.content_snapshot;
            const actions = STATUS_ACTIONS[application.status] ?? [];
            const expanded = expandedId === application.id;
            const events = eventsByApplication[application.id] ?? [];
            const needsConfirmation = actions.some((action) => action.requiresConfirmation);
            const draft = eventDrafts[application.id] ?? { eventType: "note", summary: "" };
            return (
              <article className="tracking-item" key={application.id}>
                <div className="workflow-item-heading">
                  <div>
                    <strong>{String(snapshot?.job.title ?? "Application")}</strong>
                    <span>{String(snapshot?.job.company_name ?? "Company unknown")}</span>
                  </div>
                  <span className="status-pill">{application.status}</span>
                </div>
                <div className="application-metadata">
                  <span>Revision {application.current_revision}</span>
                  {application.submitted_at && (
                    <span>Submitted {new Date(application.submitted_at).toLocaleString()}</span>
                  )}
                </div>

                {application.status === "approved" && (
                  <p className="workflow-muted">
                    Approval covers the current revision. Open the employer portal yourself before marking submission as started.
                  </p>
                )}
                {(application.status === "submitting" || application.status === "uncertain") && (
                  <p className="workflow-warning">
                    Do not guess the result. Record submitted only after you have portal confirmation evidence.
                  </p>
                )}

                {needsConfirmation && (
                  <label className="field">
                    <span>Portal confirmation reference <small>required to record submitted</small></span>
                    <input
                      value={confirmationRefs[application.id] ?? ""}
                      onChange={(event) => setConfirmationRefs((current) => ({
                        ...current,
                        [application.id]: event.target.value,
                      }))}
                      maxLength={2048}
                      placeholder="Confirmation ID or reference from the portal"
                    />
                  </label>
                )}

                {actions.length > 0 && (
                  <div className="workflow-actions tracking-actions">
                    {actions.map((action) => (
                      <button
                        className={action.status === "submitted" ? "button button-primary" : "button button-secondary"}
                        type="button"
                        key={action.status}
                        disabled={
                          busy === "status:" + application.id ||
                          (action.requiresConfirmation && !(confirmationRefs[application.id] ?? "").trim())
                        }
                        onClick={() => void transition(application, action)}
                      >
                        {busy === "status:" + application.id ? "Saving…" : action.label}
                      </button>
                    ))}
                  </div>
                )}

                <button
                  className="text-button"
                  type="button"
                  onClick={() => void toggleTimeline(application.id)}
                  disabled={busy === "timeline:" + application.id}
                >
                  {expanded ? "Hide timeline" : "Show timeline"}
                </button>

                {expanded && (
                  <div className="timeline-content">
                    <form
                      className="timeline-event-form"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void addTimelineEvent(application.id);
                      }}
                    >
                      <label className="field">
                        <span>Event type</span>
                        <select
                          value={draft.eventType}
                          onChange={(event) => setEventDrafts((current) => ({
                            ...current,
                            [application.id]: {
                              ...draft,
                              eventType: event.target.value as ApplicationTimelineEventType,
                            },
                          }))}
                        >
                          {EVENT_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Timeline note</span>
                        <textarea
                          value={draft.summary}
                          onChange={(event) => setEventDrafts((current) => ({
                            ...current,
                            [application.id]: { ...draft, summary: event.target.value },
                          }))}
                          rows={2}
                          maxLength={2000}
                          placeholder="Add a concise note, date, result or follow-up detail…"
                        />
                      </label>
                      <button
                        className="button button-secondary"
                        type="submit"
                        disabled={!draft.summary.trim() || busy === "event:" + application.id}
                      >
                        {busy === "event:" + application.id ? "Saving…" : "Add timeline event"}
                      </button>
                    </form>

                    <div className="timeline-list">
                      {events.map((event) => (
                        <div className="timeline-entry" key={event.id}>
                          <div className="timeline-entry-heading">
                            <strong>{event.event_type.replaceAll("_", " ")}</strong>
                            <span>{new Date(event.occurred_at).toLocaleString()}</span>
                          </div>
                          <p>{eventSummary(event)}</p>
                          {typeof event.metadata_json.confirmation_reference === "string" && (
                            <span className="workflow-muted">
                              Confirmation: {event.metadata_json.confirmation_reference}
                            </span>
                          )}
                        </div>
                      ))}
                      {events.length === 0 && (
                        <p className="workflow-muted">No timeline events yet. Add an interview, assessment, offer or follow-up above.</p>
                      )}
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <strong>No applications to track yet.</strong>
          <span>Prepare an application and review it before recording its lifecycle.</span>
        </div>
      )}
      <p className="workflow-disclaimer">
        Submission confirmation references are entered by you and are stored as evidence; VacancyX does not independently verify them.
      </p>
    </section>
  );
}

export default ApplicationTrackingPanel;
