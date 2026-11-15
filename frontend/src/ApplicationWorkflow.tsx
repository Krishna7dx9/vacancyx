import { useEffect, useMemo, useState } from "react";

import {
  apiRequest,
  uploadFile,
  type Application,
  type Candidate,
  type CandidateAnswer,
  type Job,
  type Resume,
  type ResumeParseResult,
} from "./api";

type Props = {
  candidate: Candidate | null;
  jobs: Job[];
  onCandidateUpdated: (candidate: Candidate) => void;
};

type ReviewDraft = {
  display_name: string;
  email: string;
  phone: string;
  location: string;
  skills: string;
};

function candidatePath(candidateId: string, suffix: string): string {
  return `/candidates/${encodeURIComponent(candidateId)}${suffix}`;
}

function reviewDraftFrom(
  candidate: Candidate,
  result: ResumeParseResult,
): ReviewDraft {
  const reviewed = result.parsed_content?.reviewed_fields;
  const suggested = result.parsed_content?.suggested_fields;
  return {
    display_name: reviewed?.display_name ?? candidate.display_name,
    email: reviewed?.email ?? suggested?.emails?.[0] ?? candidate.email ?? "",
    phone: reviewed?.phone ?? suggested?.phone_numbers?.[0] ?? candidate.phone ?? "",
    location: reviewed?.location ?? candidate.location ?? "",
    skills: reviewed?.skills?.join(", ") ?? candidate.skills.join(", "),
  };
}

function ApplicationWorkflow({ candidate, jobs, onCandidateUpdated }: Props) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [resumeParses, setResumeParses] = useState<Record<string, ResumeParseResult>>({});
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, ReviewDraft>>({});
  const [answers, setAnswers] = useState<CandidateAnswer[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);

  const [candidateEmail, setCandidateEmail] = useState("");
  const [candidatePhone, setCandidatePhone] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [answerQuestion, setAnswerQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [answerCategory, setAnswerCategory] = useState("general");

  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [selectedAnswerIds, setSelectedAnswerIds] = useState<string[]>([]);
  const [coverNote, setCoverNote] = useState("");

  const [editingApplicationId, setEditingApplicationId] = useState("");
  const [editResumeId, setEditResumeId] = useState("");
  const [editAnswerIds, setEditAnswerIds] = useState<string[]>([]);
  const [editCoverNote, setEditCoverNote] = useState("");

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId),
    [jobs, selectedJobId],
  );

  useEffect(() => {
    if (!candidate) {
      setResumes([]);
      setAnswers([]);
      setApplications([]);
      setResumeParses({});
      setReviewDrafts({});
      setCandidateEmail("");
      setCandidatePhone("");
      return;
    }
    setCandidateEmail(candidate.email ?? "");
    setCandidatePhone(candidate.phone ?? "");
    setSelectedJobId((current) =>
      jobs.some((job) => job.id === current) ? current : jobs[0]?.id ?? "",
    );

    let active = true;
    const load = async () => {
      try {
        const [resumeItems, answerItems, applicationResult] = await Promise.all([
          apiRequest<Resume[]>(candidatePath(candidate.id, "/resumes")),
          apiRequest<CandidateAnswer[]>(candidatePath(candidate.id, "/answers?active_only=true&limit=100")),
          apiRequest<{ items: Application[]; total: number }>(
            candidatePath(candidate.id, "/applications?limit=100"),
          ),
        ]);
        if (!active) return;
        setResumes(resumeItems);
        setAnswers(answerItems);
        setApplications(applicationResult.items);
        setSelectedResumeId((current) =>
          resumeItems.some((resume) => resume.id === current)
            ? current
            : resumeItems.find((resume) => resume.parse_status === "reviewed")?.id ?? "",
        );

        const parsedEntries = await Promise.all(
          resumeItems
            .filter((resume) => resume.parse_status === "parsed" || resume.parse_status === "reviewed")
            .map(async (resume) => {
              try {
                const parsed = await apiRequest<ResumeParseResult>(`/resumes/${resume.id}/parse`);
                return [resume.id, parsed] as const;
              } catch {
                return null;
              }
            }),
        );
        if (!active) return;
        const parseMap: Record<string, ResumeParseResult> = {};
        const drafts: Record<string, ReviewDraft> = {};
        for (const entry of parsedEntries) {
          if (!entry) continue;
          parseMap[entry[0]] = entry[1];
          drafts[entry[0]] = reviewDraftFrom(candidate, entry[1]);
        }
        setResumeParses(parseMap);
        setReviewDrafts(drafts);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load application materials.");
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [candidate?.id, jobs, candidate?.email, candidate?.phone]);

  async function refreshApplications() {
    if (!candidate) return;
    const result = await apiRequest<{ items: Application[]; total: number }>(
      candidatePath(candidate.id, "/applications?limit=100"),
    );
    setApplications(result.items);
  }

  async function saveCandidateContact(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate) return;
    setBusy("contact");
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<Candidate>(`/candidates/${candidate.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          email: candidateEmail.trim() || null,
          phone: candidatePhone.trim() || null,
        }),
      });
      onCandidateUpdated(updated);
      setNotice("Candidate contact details saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update candidate contact details.");
    } finally {
      setBusy(null);
    }
  }

  async function uploadResume(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate || !resumeFile) return;
    setBusy("upload");
    setError("");
    setNotice("");
    try {
      const uploaded = await uploadFile<Resume>(
        candidatePath(candidate.id, "/resumes"),
        resumeFile,
      );
      setResumes((current) => [uploaded, ...current]);
      setSelectedResumeId(uploaded.id);
      setResumeFile(null);
      setNotice("Resume uploaded to private local storage. Parse it to review extracted fields.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Resume upload failed.");
    } finally {
      setBusy(null);
    }
  }

  async function parseResume(resume: Resume) {
    setBusy(`parse:${resume.id}`);
    setError("");
    setNotice("");
    try {
      const parsed = await apiRequest<ResumeParseResult>(`/resumes/${resume.id}/parse`, {
        method: "POST",
      });
      setResumeParses((current) => ({ ...current, [resume.id]: parsed }));
      setReviewDrafts((current) => ({
        ...current,
        [resume.id]: reviewDraftFrom(candidate!, parsed),
      }));
      setResumes((current) =>
        current.map((item) => item.id === resume.id ? { ...item, parse_status: parsed.parse_status } : item),
      );
      setNotice("Resume parsed locally. Review the suggested fields before marking it reviewed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Resume parsing failed.");
    } finally {
      setBusy(null);
    }
  }

  function updateReviewDraft(resumeId: string, field: keyof ReviewDraft, value: string) {
    setReviewDrafts((current) => ({
      ...current,
      [resumeId]: { ...current[resumeId], [field]: value },
    }));
  }

  async function saveResumeReview(resume: Resume) {
    if (!candidate) return;
    const draft = reviewDrafts[resume.id];
    if (!draft) return;
    setBusy(`review:${resume.id}`);
    setError("");
    setNotice("");
    try {
      const parsed = await apiRequest<ResumeParseResult>(`/resumes/${resume.id}/parse/review`, {
        method: "PATCH",
        body: JSON.stringify({
          display_name: draft.display_name,
          email: draft.email.trim() || null,
          phone: draft.phone.trim() || null,
          location: draft.location.trim() || null,
          skills: draft.skills.split(",").map((value) => value.trim()).filter(Boolean),
        }),
      });
      setResumeParses((current) => ({ ...current, [resume.id]: parsed }));
      setResumes((current) =>
        current.map((item) => item.id === resume.id ? { ...item, parse_status: "reviewed" } : item),
      );
      setNotice("Resume fields marked reviewed. Candidate profile contact details remain separately editable above.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save resume review.");
    } finally {
      setBusy(null);
    }
  }

  async function createAnswer(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate) return;
    setBusy("answer");
    setError("");
    setNotice("");
    try {
      const answer = await apiRequest<CandidateAnswer>(candidatePath(candidate.id, "/answers"), {
        method: "POST",
        body: JSON.stringify({
          question: answerQuestion,
          answer_text: answerText,
          category: answerCategory.trim() || null,
          tags: [],
        }),
      });
      setAnswers((current) => [answer, ...current]);
      setSelectedAnswerIds((current) => [...current, answer.id]);
      setAnswerQuestion("");
      setAnswerText("");
      setNotice("Reusable answer saved and selected for the application draft.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save reusable answer.");
    } finally {
      setBusy(null);
    }
  }

  function toggleAnswer(answerId: string, editing = false) {
    const setter = editing ? setEditAnswerIds : setSelectedAnswerIds;
    setter((current) =>
      current.includes(answerId)
        ? current.filter((value) => value !== answerId)
        : [...current, answerId],
    );
  }

  async function prepareApplication(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate || !selectedJobId) return;
    setBusy("prepare");
    setError("");
    setNotice("");
    try {
      const created = await apiRequest<Application>(candidatePath(candidate.id, "/applications"), {
        method: "POST",
        body: JSON.stringify({
          job_id: selectedJobId,
          resume_id: selectedResumeId || null,
          answer_ids: selectedAnswerIds,
          custom_fields: coverNote.trim() ? { cover_note: coverNote.trim() } : {},
        }),
      });
      setApplications((current) => [created, ...current]);
      setCoverNote("");
      setNotice("Application draft prepared. Review its snapshot and readiness warnings below.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not prepare application.");
    } finally {
      setBusy(null);
    }
  }

  function beginEdit(application: Application) {
    const snapshot = application.latest_revision?.content_snapshot;
    if (!snapshot) return;
    setEditingApplicationId(application.id);
    setEditResumeId(application.resume_id ?? "");
    setEditAnswerIds(snapshot.answers.map((answer) => answer.id));
    setEditCoverNote(snapshot.custom_fields.cover_note ?? "");
  }

  async function saveApplicationRevision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate || !editingApplicationId) return;
    setBusy("revise");
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<Application>(
        candidatePath(candidate.id, `/applications/${editingApplicationId}`),
        {
          method: "PATCH",
          body: JSON.stringify({
            resume_id: editResumeId || null,
            answer_ids: editAnswerIds,
            custom_fields: editCoverNote.trim() ? { cover_note: editCoverNote.trim() } : {},
          }),
        },
      );
      setApplications((current) =>
        current.map((item) => item.id === updated.id ? updated : item),
      );
      setEditingApplicationId("");
      setNotice(`Draft revised to content revision ${updated.current_revision}. Any prior review must be repeated.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not revise application.");
    } finally {
      setBusy(null);
    }
  }

  if (!candidate) {
    return (
      <section className="panel workflow-panel">
        <div className="panel-heading">
          <div><p className="section-kicker">05 / APPLICATION WORKFLOW</p><h2>Prepare applications</h2></div>
        </div>
        <div className="empty-state"><strong>Select or create a candidate profile.</strong><span>Application materials and drafts are scoped to the active candidate.</span></div>
      </section>
    );
  }

  return (
    <section className="panel workflow-panel">
      <div className="panel-heading">
        <div><p className="section-kicker">05 / APPLICATION WORKFLOW</p><h2>Prepare and review applications</h2></div>
        <span className="result-count">{applications.length} prepared</span>
      </div>

      {(error || notice) && (
        <div className={error ? "feedback feedback-error" : "feedback feedback-success"} role="status">
          <span>{error || notice}</span>
          <button type="button" className="feedback-close" onClick={() => { setError(""); setNotice(""); }}>Dismiss</button>
        </div>
      )}

      <div className="workflow-grid">
        <div className="workflow-column">
          <section className="workflow-subpanel">
            <h3>Candidate contact details</h3>
            <p className="workflow-muted">These values are copied into a new application snapshot. Resume review does not silently overwrite this profile.</p>
            <form className="workflow-form" onSubmit={saveCandidateContact}>
              <label className="field"><span>Email</span><input type="email" value={candidateEmail} onChange={(event) => setCandidateEmail(event.target.value)} placeholder="name@example.com" /></label>
              <label className="field"><span>Phone</span><input value={candidatePhone} onChange={(event) => setCandidatePhone(event.target.value)} placeholder="Phone number" /></label>
              <button className="button button-secondary" type="submit" disabled={busy === "contact"}>{busy === "contact" ? "Saving…" : "Save contact details"}</button>
            </form>
          </section>

          <section className="workflow-subpanel">
            <h3>Resume library</h3>
            <form className="workflow-form" onSubmit={uploadResume}>
              <label className="field">
                <span>Upload PDF, DOCX or TXT</span>
                <input type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)} />
              </label>
              <button className="button button-secondary" type="submit" disabled={!resumeFile || busy === "upload"}>{busy === "upload" ? "Uploading…" : "Upload resume"}</button>
            </form>
            {resumes.length ? (
              <div className="workflow-list">
                {resumes.map((resume) => {
                  const parsed = resumeParses[resume.id];
                  const draft = reviewDrafts[resume.id];
                  return (
                    <article className="workflow-item" key={resume.id}>
                      <div className="workflow-item-heading">
                        <div><strong>{resume.original_filename}</strong><span>{(resume.file_size_bytes / 1024).toFixed(0)} KB · {resume.parse_status}</span></div>
                        <span className={resume.parse_status === "reviewed" ? "status-pill status-active" : "status-pill"}>{resume.parse_status}</span>
                      </div>
                      {resume.parse_status === "uploaded" || resume.parse_status === "failed" ? (
                        <button className="text-button" type="button" onClick={() => void parseResume(resume)} disabled={busy === `parse:${resume.id}`}>
                          {busy === `parse:${resume.id}` ? "Parsing…" : "Parse locally"}
                        </button>
                      ) : null}
                      {parsed && draft && (
                        <div className="review-fields">
                          <p className="workflow-muted">Confirm or correct extracted suggestions. Nothing is copied to the candidate profile automatically.</p>
                          <label className="field"><span>Name</span><input value={draft.display_name} onChange={(event) => updateReviewDraft(resume.id, "display_name", event.target.value)} /></label>
                          <label className="field"><span>Email</span><input value={draft.email} onChange={(event) => updateReviewDraft(resume.id, "email", event.target.value)} /></label>
                          <label className="field"><span>Phone</span><input value={draft.phone} onChange={(event) => updateReviewDraft(resume.id, "phone", event.target.value)} /></label>
                          <label className="field"><span>Location</span><input value={draft.location} onChange={(event) => updateReviewDraft(resume.id, "location", event.target.value)} /></label>
                          <label className="field"><span>Skills <small>comma-separated</small></span><input value={draft.skills} onChange={(event) => updateReviewDraft(resume.id, "skills", event.target.value)} /></label>
                          <button className="button button-secondary" type="button" onClick={() => void saveResumeReview(resume)} disabled={busy === `review:${resume.id}`}>
                            {busy === `review:${resume.id}` ? "Saving…" : "Confirm reviewed fields"}
                          </button>
                          {parsed.parsed_content?.warnings?.map((warning) => <span className="workflow-warning" key={warning}>{warning}</span>)}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : <p className="workflow-muted">No resumes uploaded for this candidate yet.</p>}
          </section>

          <section className="workflow-subpanel">
            <h3>Reusable answers</h3>
            <p className="workflow-muted">Save reviewed answers once and select them for relevant applications.</p>
            <form className="workflow-form" onSubmit={createAnswer}>
              <label className="field"><span>Question</span><input value={answerQuestion} onChange={(event) => setAnswerQuestion(event.target.value)} required maxLength={500} placeholder="Why are you interested in this role?" /></label>
              <label className="field"><span>Answer</span><textarea value={answerText} onChange={(event) => setAnswerText(event.target.value)} required maxLength={10000} rows={4} placeholder="Write an accurate answer based on your experience…" /></label>
              <label className="field"><span>Category</span><input value={answerCategory} onChange={(event) => setAnswerCategory(event.target.value)} maxLength={80} /></label>
              <button className="button button-secondary" type="submit" disabled={busy === "answer"}>{busy === "answer" ? "Saving…" : "Save reusable answer"}</button>
            </form>
            <div className="workflow-list">
              {answers.map((answer) => (
                <article className="workflow-item" key={answer.id}>
                  <strong>{answer.question}</strong>
                  <p>{answer.answer_text}</p>
                  <span>Revision {answer.current_revision} · {answer.category || "Uncategorised"}</span>
                </article>
              ))}
              {answers.length === 0 && <p className="workflow-muted">No reusable answers saved yet.</p>}
            </div>
          </section>
        </div>

        <div className="workflow-column">
          <section className="workflow-subpanel">
            <h3>Prepare a new application</h3>
            <p className="workflow-muted">Choose an indexed job and candidate-owned material. VacancyX creates a point-in-time snapshot; it does not submit externally.</p>
            <form className="workflow-form" onSubmit={prepareApplication}>
              <label className="field">
                <span>Open job</span>
                <select value={selectedJobId} onChange={(event) => setSelectedJobId(event.target.value)} required>
                  <option value="">Select a job</option>
                  {jobs.filter((job) => job.status === "open").map((job) => <option key={job.id} value={job.id}>{job.title} — {job.company_name}</option>)}
                </select>
              </label>
              {selectedJob && <p className="workflow-muted">{selectedJob.location || "Location unknown"} · {selectedJob.work_mode || "Work mode unknown"}</p>}
              <label className="field">
                <span>Resume</span>
                <select value={selectedResumeId} onChange={(event) => setSelectedResumeId(event.target.value)}>
                  <option value="">No resume selected</option>
                  {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.original_filename} ({resume.parse_status})</option>)}
                </select>
              </label>
              <fieldset className="answer-picker">
                <legend>Reusable answers</legend>
                {answers.map((answer) => (
                  <label className="check-row" key={answer.id}>
                    <input type="checkbox" checked={selectedAnswerIds.includes(answer.id)} onChange={() => toggleAnswer(answer.id)} />
                    <span>{answer.question}</span>
                  </label>
                ))}
                {answers.length === 0 && <p className="workflow-muted">Save answers in the library first, or prepare without them.</p>}
              </fieldset>
              <label className="field">
                <span>Additional application note <small>optional</small></span>
                <textarea value={coverNote} onChange={(event) => setCoverNote(event.target.value)} rows={3} maxLength={4000} placeholder="A tailored note to include in the application snapshot…" />
              </label>
              <button className="button button-primary" type="submit" disabled={!selectedJobId || busy === "prepare"}>{busy === "prepare" ? "Preparing…" : "Prepare application draft"}</button>
            </form>
          </section>

          <section className="workflow-subpanel">
            <div className="workflow-section-heading"><h3>Prepared applications</h3><span>{applications.length}</span></div>
            {applications.length ? (
              <div className="workflow-list">
                {applications.map((application) => {
                  const snapshot = application.latest_revision?.content_snapshot;
                  const readiness = snapshot?.readiness;
                  const editing = editingApplicationId === application.id;
                  return (
                    <article className="workflow-item application-item" key={application.id}>
                      <div className="workflow-item-heading">
                        <div><strong>{String(snapshot?.job.title ?? "Application draft")}</strong><span>{String(snapshot?.job.company_name ?? "Company unknown")}</span></div>
                        <span className="status-pill">{application.status}</span>
                      </div>
                      <div className="application-metadata">
                        <span>Revision {application.current_revision}</span>
                        <span>{snapshot?.answers.length ?? 0} answers</span>
                        <span className={readiness?.status === "ready_for_review" ? "status-pill status-active" : "status-pill status-needs-review"}>{readiness?.status === "ready_for_review" ? "Ready for review" : "Needs attention"}</span>
                      </div>
                      {readiness?.missing_fields.length ? <p className="workflow-warning">Missing: {readiness.missing_fields.join(", ")}</p> : null}
                      {application.latest_revision && <p className="hash-line">SHA-256 · {application.latest_revision.content_hash}</p>}
                      {editing ? (
                        <form className="workflow-form revision-form" onSubmit={saveApplicationRevision}>
                          <label className="field"><span>Resume</span><select value={editResumeId} onChange={(event) => setEditResumeId(event.target.value)}><option value="">No resume selected</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.original_filename} ({resume.parse_status})</option>)}</select></label>
                          <fieldset className="answer-picker"><legend>Selected answers</legend>{answers.map((answer) => <label className="check-row" key={answer.id}><input type="checkbox" checked={editAnswerIds.includes(answer.id)} onChange={() => toggleAnswer(answer.id, true)} /><span>{answer.question}</span></label>)}</fieldset>
                          <label className="field"><span>Additional application note</span><textarea rows={3} value={editCoverNote} onChange={(event) => setEditCoverNote(event.target.value)} maxLength={4000} /></label>
                          <div className="workflow-actions"><button className="button button-primary" type="submit" disabled={busy === "revise"}>{busy === "revise" ? "Saving…" : "Save new revision"}</button><button className="text-button" type="button" onClick={() => setEditingApplicationId("")}>Cancel</button></div>
                        </form>
                      ) : (
                        <div className="workflow-actions">
                          {["prepared", "ready_for_review"].includes(application.status) && <button className="text-button" type="button" onClick={() => beginEdit(application)}>Edit draft</button>}
                          {snapshot?.job && typeof snapshot.job.canonical_url === "string" && <a className="job-link" href={snapshot.job.canonical_url} target="_blank" rel="noreferrer">Original listing ↗</a>}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : <div className="empty-state"><strong>No application drafts yet.</strong><span>Prepare one from an open job above.</span></div>}
          </section>
        </div>
      </div>
      <p className="workflow-disclaimer">External submission is intentionally unavailable at this stage. Review each snapshot carefully; editing creates a new revision and requires a fresh review.</p>
    </section>
  );
}

export default ApplicationWorkflow;
