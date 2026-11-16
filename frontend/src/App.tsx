import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import ApplicationWorkflow from "./ApplicationWorkflow";
import DiscoveryPanel from "./DiscoveryPanel";

import {
  apiRequest,
  type Candidate,
  type Job,
  type JobSearchResponse,
  type MatchCriteria,
  type SearchProfile,
  type SearchProfileMatchResponse,
} from "./api";

function splitTerms(value: string): string[] {
  return value.split(",").map((term) => term.trim()).filter(Boolean);
}

function salaryLabel(job: Job): string {
  if (job.salary_min === null && job.salary_max === null) return "Salary not disclosed";
  const currency = job.salary_currency ?? "Unspecified currency";
  const minimum = job.salary_min?.toLocaleString() ?? "—";
  const maximum = job.salary_max?.toLocaleString() ?? "—";
  return `${currency} ${minimum} – ${maximum}`;
}

function App() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [jobs, setJobs] = useState<JobSearchResponse | null>(null);
  const [matches, setMatches] = useState<SearchProfileMatchResponse | null>(null);

  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [candidatePhone, setCandidatePhone] = useState("");
  const [candidateSkills, setCandidateSkills] = useState("");
  const [candidateLocation, setCandidateLocation] = useState("");
  const [candidateEditOpen, setCandidateEditOpen] = useState(false);
  const [editCandidateName, setEditCandidateName] = useState("");
  const [editCandidateEmail, setEditCandidateEmail] = useState("");
  const [editCandidatePhone, setEditCandidatePhone] = useState("");
  const [editCandidateLocation, setEditCandidateLocation] = useState("");
  const [editCandidateSkills, setEditCandidateSkills] = useState("");
  const [searchEditOpen, setSearchEditOpen] = useState(false);
  const [editProfileName, setEditProfileName] = useState("");
  const [editProfileEnabled, setEditProfileEnabled] = useState(true);
  const [editProfileCriteria, setEditProfileCriteria] = useState<MatchCriteria>({
    target_titles: [],
    excluded_keywords: [],
    required_skills: [],
    allowed_locations: [],
    work_modes: [],
    employment_types: [],
  });
  const [editMinimumSalary, setEditMinimumSalary] = useState("");
  const [editSalaryCurrency, setEditSalaryCurrency] = useState("");
  const [profileName, setProfileName] = useState("My software engineering search");
  const [targetTitles, setTargetTitles] = useState("");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [excludedKeywords, setExcludedKeywords] = useState("");
  const [allowedLocations, setAllowedLocations] = useState("");
  const [workModes, setWorkModes] = useState("");
  const [employmentTypes, setEmploymentTypes] = useState("");
  const [minimumSalary, setMinimumSalary] = useState("");
  const [salaryCurrency, setSalaryCurrency] = useState("");

  const [jobQuery, setJobQuery] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<Candidate[]>("/candidates"),
      apiRequest<JobSearchResponse>("/jobs?limit=20"),
    ])
      .then(([candidateItems, jobItems]) => {
        if (!active) return;
        setCandidates(candidateItems);
        setSelectedCandidateId(candidateItems[0]?.id ?? "");
        setJobs(jobItems);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load workspace.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCandidateId) {
      setProfiles([]);
      setSelectedProfileId("");
      setMatches(null);
      return;
    }
    let active = true;
    setMatches(null);
    apiRequest<SearchProfile[]>(
      `/candidates/${encodeURIComponent(selectedCandidateId)}/search-profiles`,
    )
      .then((items) => {
        if (!active) return;
        setProfiles(items);
        setSelectedProfileId(items[0]?.id ?? "");
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load search profiles.");
      });
    return () => {
      active = false;
    };
  }, [selectedCandidateId]);

  async function createCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("candidate");
    setError("");
    setNotice("");
    try {
      const candidate = await apiRequest<Candidate>("/candidates", {
        method: "POST",
        body: JSON.stringify({
          display_name: candidateName,
          email: candidateEmail.trim() || null,
          phone: candidatePhone.trim() || null,
          skills: splitTerms(candidateSkills),
          location: candidateLocation.trim() || null,
        }),
      });
      setCandidates((current) => [...current, candidate]);
      setSelectedCandidateId(candidate.id);
      setCandidateName("");
      setCandidateEmail("");
      setCandidatePhone("");
      setCandidateSkills("");
      setCandidateLocation("");
      setNotice("Candidate profile created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create candidate profile.");
    } finally {
      setBusy(null);
    }
  }

  function openCandidateEditor() {
    if (!selectedCandidate) return;
    setEditCandidateName(selectedCandidate.display_name);
    setEditCandidateEmail(selectedCandidate.email ?? "");
    setEditCandidatePhone(selectedCandidate.phone ?? "");
    setEditCandidateLocation(selectedCandidate.location ?? "");
    setEditCandidateSkills(selectedCandidate.skills.join(", "));
    setCandidateEditOpen(true);
  }

  async function updateCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidateId) return;
    setBusy("candidate-edit");
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<Candidate>(
        "/candidates/" + encodeURIComponent(selectedCandidateId),
        {
          method: "PATCH",
          body: JSON.stringify({
            display_name: editCandidateName.trim(),
            email: editCandidateEmail.trim() || null,
            phone: editCandidatePhone.trim() || null,
            location: editCandidateLocation.trim() || null,
            skills: splitTerms(editCandidateSkills),
          }),
        },
      );
      setCandidates((current) => current.map((item) => item.id === updated.id ? updated : item));
      setCandidateEditOpen(false);
      setNotice("Candidate profile updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update candidate profile.");
    } finally {
      setBusy(null);
    }
  }

  function openSearchEditor() {
    if (!selectedProfile) return;
    setEditProfileName(selectedProfile.name);
    setEditProfileEnabled(selectedProfile.is_enabled);
    setEditProfileCriteria({
      target_titles: [...selectedProfile.criteria.target_titles],
      excluded_keywords: [...selectedProfile.criteria.excluded_keywords],
      required_skills: [...selectedProfile.criteria.required_skills],
      allowed_locations: [...selectedProfile.criteria.allowed_locations],
      work_modes: [...selectedProfile.criteria.work_modes],
      employment_types: [...selectedProfile.criteria.employment_types],
      ...(selectedProfile.criteria.minimum_salary !== undefined
        ? { minimum_salary: selectedProfile.criteria.minimum_salary }
        : {}),
      ...(selectedProfile.criteria.salary_currency
        ? { salary_currency: selectedProfile.criteria.salary_currency }
        : {}),
    });
    setEditMinimumSalary(
      selectedProfile.criteria.minimum_salary === undefined
        ? ""
        : String(selectedProfile.criteria.minimum_salary),
    );
    setEditSalaryCurrency(selectedProfile.criteria.salary_currency ?? "");
    setSearchEditOpen(true);
  }

  async function updateSearchProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidateId || !selectedProfileId) return;
    if (editMinimumSalary.trim()) {
      const amount = Number(editMinimumSalary);
      if (!Number.isFinite(amount) || amount < 0) {
        setError("Enter a valid non-negative minimum salary.");
        return;
      }
      if (!/^[A-Za-z]{3}$/.test(editSalaryCurrency.trim())) {
        setError("Enter a three-letter currency with the minimum salary.");
        return;
      }
    }
    const criteria: MatchCriteria = {
      ...editProfileCriteria,
      ...(editMinimumSalary.trim()
        ? {
            minimum_salary: Number(editMinimumSalary),
            salary_currency: editSalaryCurrency.trim().toUpperCase(),
          }
        : {}),
    };
    if (!editMinimumSalary.trim()) {
      delete criteria.minimum_salary;
      delete criteria.salary_currency;
    }
    setBusy("profile-edit");
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<SearchProfile>(
        "/candidates/" + encodeURIComponent(selectedCandidateId)
          + "/search-profiles/" + encodeURIComponent(selectedProfileId),
        {
          method: "PATCH",
          body: JSON.stringify({
            name: editProfileName.trim(),
            is_enabled: editProfileEnabled,
            criteria,
          }),
        },
      );
      setProfiles((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSearchEditOpen(false);
      setMatches(null);
      setNotice("Saved search profile updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update search profile.");
    } finally {
      setBusy(null);
    }
  }

  async function createSearchProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidateId) return;
    if (minimumSalary.trim()) {
      const amount = Number(minimumSalary);
      if (!Number.isFinite(amount) || amount < 0) {
        setError("Enter a valid non-negative minimum salary.");
        return;
      }
      if (!/^[A-Za-z]{3}$/.test(salaryCurrency.trim())) {
        setError("Enter a three-letter currency with the minimum salary.");
        return;
      }
    }
    setBusy("profile");
    setError("");
    setNotice("");
    const criteria: MatchCriteria = {
      target_titles: splitTerms(targetTitles),
      excluded_keywords: splitTerms(excludedKeywords),
      required_skills: splitTerms(requiredSkills),
      allowed_locations: splitTerms(allowedLocations),
      work_modes: splitTerms(workModes),
      employment_types: splitTerms(employmentTypes),
    };
    if (minimumSalary.trim()) {
      criteria.minimum_salary = Number(minimumSalary);
      criteria.salary_currency = salaryCurrency.trim().toUpperCase();
    }
    try {
      const profile = await apiRequest<SearchProfile>(
        `/candidates/${encodeURIComponent(selectedCandidateId)}/search-profiles`,
        { method: "POST", body: JSON.stringify({ name: profileName, criteria }) },
      );
      setProfiles((current) => [profile, ...current]);
      setSelectedProfileId(profile.id);
      setMatches(null);
      setNotice("Search profile saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save search profile.");
    } finally {
      setBusy(null);
    }
  }

  async function refreshJobs() {
    setBusy("jobs");
    setError("");
    setNotice("");
    const params = new URLSearchParams({ limit: "50" });
    if (jobQuery.trim()) params.set("query", jobQuery.trim());
    if (jobLocation.trim()) params.set("location", jobLocation.trim());
    try {
      const result = await apiRequest<JobSearchResponse>(`/jobs?${params.toString()}`);
      setJobs(result);
      setMatches(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Job search failed.");
      throw cause;
    } finally {
      setBusy(null);
    }
  }

  async function searchJobs(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await refreshJobs();
    } catch {
      // refreshJobs already exposes the failure in the workspace feedback.
    }
  }

  async function evaluateMatches() {
    if (!selectedCandidateId || !selectedProfileId) return;
    setBusy("matches");
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<SearchProfileMatchResponse>(
        `/candidates/${encodeURIComponent(selectedCandidateId)}/search-profiles/${encodeURIComponent(selectedProfileId)}/matches?limit=50`,
        { method: "POST" },
      );
      setMatches(result);
      setNotice(`Evaluated ${result.evaluated_count} jobs using rule set v1.0.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Match evaluation failed.");
    } finally {
      setBusy(null);
    }
  }

  const selectedCandidate = candidates.find((item) => item.id === selectedCandidateId);
  const selectedProfile = profiles.find((item) => item.id === selectedProfileId);

  return (
    <main className="workspace">
      <header className="topbar">
        <a className="brand" href="/" aria-label="VacancyX home">
          <span className="brand-mark">V</span>
          VacancyX
        </a>
        <div className="topbar-meta">
          <span className="local-indicator"><span /> Local workspace</span>
          <span className="privacy-label">Your data stays on this machine</span>
        </div>
      </header>

      <section className="intro">
        <div>
          <p className="eyebrow">JOB SEARCH WORKSPACE</p>
          <h1>Find the right role.<br /><span>Know why it fits.</span></h1>
          <p className="intro-copy">
            Configure your profile once, search normalized opportunities, and inspect
            explainable eligibility before deciding what deserves your time.
          </p>
        </div>
        <div className="intro-stat">
          <span className="stat-label">Jobs in your workspace</span>
          <strong>{jobs?.total ?? "—"}</strong>
          <span className="stat-footnote">Open listings currently indexed</span>
        </div>
      </section>

      {(error || notice) && (
        <div className={error ? "feedback feedback-error" : "feedback feedback-success"} role="status">
          <span>{error || notice}</span>
          <button type="button" className="feedback-close" onClick={() => { setError(""); setNotice(""); }}>
            Dismiss
          </button>
        </div>
      )}

      <div className="workspace-grid">
        <aside className="sidebar">
          <section className="panel">
            <div className="panel-heading">
              <div><p className="section-kicker">01 / CANDIDATE</p><h2>Your profile</h2></div>
              <span className="step-icon">01</span>
            </div>
            {candidates.length > 0 && (
              <label className="field">
                <span>Active candidate</span>
                <select value={selectedCandidateId} onChange={(event) => setSelectedCandidateId(event.target.value)}>
                  {candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>{candidate.display_name}</option>
                  ))}
                </select>
              </label>
            )}
            {selectedCandidate && (
              <div className="candidate-summary">
                <strong>{selectedCandidate.display_name}</strong>
                <span>{selectedCandidate.location || "Location not set"}</span>
                <div className="chip-list">
                  {selectedCandidate.skills.slice(0, 8).map((skill) => <span className="chip" key={skill}>{skill}</span>)}
                  {selectedCandidate.skills.length === 0 && <span className="muted">No skills added yet</span>}
                </div>
              </div>
            )}
            {selectedCandidate && (
              <>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => candidateEditOpen ? setCandidateEditOpen(false) : openCandidateEditor()}
                >
                  {candidateEditOpen ? "Cancel profile edit" : "Edit active profile"}
                </button>
                {candidateEditOpen && (
                  <form onSubmit={(event) => void updateCandidate(event)} className="stack-form editor-form">
                    <label className="field">
                      <span>Display name</span>
                      <input value={editCandidateName} onChange={(event) => setEditCandidateName(event.target.value)} required maxLength={160} />
                    </label>
                    <label className="field">
                      <span>Email</span>
                      <input type="email" value={editCandidateEmail} onChange={(event) => setEditCandidateEmail(event.target.value)} />
                    </label>
                    <label className="field">
                      <span>Phone</span>
                      <input value={editCandidatePhone} onChange={(event) => setEditCandidatePhone(event.target.value)} />
                    </label>
                    <label className="field">
                      <span>Current location</span>
                      <input value={editCandidateLocation} onChange={(event) => setEditCandidateLocation(event.target.value)} />
                    </label>
                    <label className="field">
                      <span>Skills <small>comma-separated</small></span>
                      <input value={editCandidateSkills} onChange={(event) => setEditCandidateSkills(event.target.value)} />
                    </label>
                    <button className="button button-primary" type="submit" disabled={busy === "candidate-edit"}>
                      {busy === "candidate-edit" ? "Saving…" : "Save profile changes"}
                    </button>
                  </form>
                )}
              </>
            )}
            <details className="editor">
              <summary>{candidates.length ? "Add another candidate" : "Create your first candidate profile"}</summary>
              <form onSubmit={createCandidate} className="stack-form">
                <label className="field">
                  <span>Display name</span>
                  <input value={candidateName} onChange={(event) => setCandidateName(event.target.value)} required maxLength={160} />
                </label>
                <label className="field">
                  <span>Email <small>optional</small></span>
                  <input type="email" value={candidateEmail} onChange={(event) => setCandidateEmail(event.target.value)} placeholder="name@example.com" />
                </label>
                <label className="field">
                  <span>Phone <small>optional</small></span>
                  <input value={candidatePhone} onChange={(event) => setCandidatePhone(event.target.value)} placeholder="Phone number" />
                </label>
                <label className="field">
                  <span>Skills <small>comma-separated</small></span>
                  <input value={candidateSkills} onChange={(event) => setCandidateSkills(event.target.value)} placeholder="Python, SQL, FastAPI" />
                </label>
                <label className="field">
                  <span>Current location <small>optional</small></span>
                  <input value={candidateLocation} onChange={(event) => setCandidateLocation(event.target.value)} placeholder="City, country" />
                </label>
                <button className="button button-secondary" type="submit" disabled={busy === "candidate"}>
                  {busy === "candidate" ? "Saving…" : "Save candidate"}
                </button>
              </form>
            </details>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div><p className="section-kicker">02 / SEARCH RULES</p><h2>Search profile</h2></div>
              <span className="step-icon">02</span>
            </div>
            {profiles.length > 0 && (
              <label className="field">
                <span>Saved search</span>
                <select value={selectedProfileId} onChange={(event) => { setSelectedProfileId(event.target.value); setMatches(null); }}>
                  {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
                </select>
              </label>
            )}
            {selectedProfile && (
              <div className="profile-status">
                <span className={selectedProfile.is_enabled ? "status-pill status-active" : "status-pill"}>
                  {selectedProfile.is_enabled ? "Enabled" : "Disabled"}
                </span>
                <span>{selectedProfile.criteria.target_titles?.length ?? 0} target titles</span>
              </div>
            )}
            {selectedProfile && (
              <>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => searchEditOpen ? setSearchEditOpen(false) : openSearchEditor()}
                >
                  {searchEditOpen ? "Cancel search edit" : "Edit saved search"}
                </button>
                {searchEditOpen && (
                  <form onSubmit={(event) => void updateSearchProfile(event)} className="stack-form editor-form">
                    <label className="field">
                      <span>Search name</span>
                      <input value={editProfileName} onChange={(event) => setEditProfileName(event.target.value)} required maxLength={120} />
                    </label>
                    <label className="field">
                      <span>Target job titles <small>comma-separated</small></span>
                      <input value={editProfileCriteria.target_titles.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, target_titles: splitTerms(event.target.value) }))} />
                    </label>
                    <label className="field">
                      <span>Required job skills</span>
                      <input value={editProfileCriteria.required_skills.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, required_skills: splitTerms(event.target.value) }))} />
                    </label>
                    <label className="field">
                      <span>Exclude keywords</span>
                      <input value={editProfileCriteria.excluded_keywords.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, excluded_keywords: splitTerms(event.target.value) }))} />
                    </label>
                    <label className="field">
                      <span>Allowed locations</span>
                      <input value={editProfileCriteria.allowed_locations.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, allowed_locations: splitTerms(event.target.value) }))} />
                    </label>
                    <div className="field-row">
                      <label className="field">
                        <span>Work modes</span>
                        <input value={editProfileCriteria.work_modes.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, work_modes: splitTerms(event.target.value) }))} />
                      </label>
                      <label className="field">
                        <span>Employment types</span>
                        <input value={editProfileCriteria.employment_types.join(", ")} onChange={(event) => setEditProfileCriteria((current) => ({ ...current, employment_types: splitTerms(event.target.value) }))} />
                      </label>
                    </div>
                    <div className="field-row">
                      <label className="field">
                        <span>Minimum salary</span>
                        <input type="number" min="0" value={editMinimumSalary} onChange={(event) => setEditMinimumSalary(event.target.value)} placeholder="Optional" />
                      </label>
                      <label className="field">
                        <span>Currency</span>
                        <input value={editSalaryCurrency} onChange={(event) => setEditSalaryCurrency(event.target.value.toUpperCase())} maxLength={3} placeholder="INR, USD…" />
                      </label>
                    </div>
                    <label className="check-row">
                      <input type="checkbox" checked={editProfileEnabled} onChange={(event) => setEditProfileEnabled(event.target.checked)} />
                      <span>Search profile enabled</span>
                    </label>
                    <button className="button button-primary" type="submit" disabled={busy === "profile-edit"}>
                      {busy === "profile-edit" ? "Saving…" : "Save search changes"}
                    </button>
                  </form>
                )}
              </>
            )}
            <details className="editor" open={profiles.length === 0}>
              <summary>{profiles.length ? "Create another search profile" : "Configure your first search"}</summary>
              <form onSubmit={createSearchProfile} className="stack-form">
                <label className="field">
                  <span>Search name</span>
                  <input value={profileName} onChange={(event) => setProfileName(event.target.value)} required maxLength={120} />
                </label>
                <label className="field">
                  <span>Target job titles <small>comma-separated</small></span>
                  <input value={targetTitles} onChange={(event) => setTargetTitles(event.target.value)} placeholder="Backend Engineer, Software Engineer" />
                </label>
                <label className="field">
                  <span>Required job skills <small>hard filter</small></span>
                  <input value={requiredSkills} onChange={(event) => setRequiredSkills(event.target.value)} placeholder="Python, SQL" />
                </label>
                <label className="field">
                  <span>Exclude keywords</span>
                  <input value={excludedKeywords} onChange={(event) => setExcludedKeywords(event.target.value)} placeholder="Internship, unpaid" />
                </label>
                <label className="field">
                  <span>Allowed locations</span>
                  <input value={allowedLocations} onChange={(event) => setAllowedLocations(event.target.value)} placeholder="Remote, Bengaluru, India" />
                </label>
                <div className="field-row">
                  <label className="field">
                    <span>Work modes</span>
                    <input value={workModes} onChange={(event) => setWorkModes(event.target.value)} placeholder="Remote, Hybrid" />
                  </label>
                  <label className="field">
                    <span>Employment</span>
                    <input value={employmentTypes} onChange={(event) => setEmploymentTypes(event.target.value)} placeholder="Full-time" />
                  </label>
                </div>
                <div className="field-row">
                  <label className="field">
                    <span>Minimum salary</span>
                    <input type="number" min="0" value={minimumSalary} onChange={(event) => setMinimumSalary(event.target.value)} placeholder="Optional" />
                  </label>
                  <label className="field">
                    <span>Currency</span>
                    <input value={salaryCurrency} onChange={(event) => setSalaryCurrency(event.target.value.toUpperCase())} placeholder="INR, USD…" maxLength={3} />
                  </label>
                </div>
                <p className="field-hint">A salary floor requires a three-letter currency. Unknown salary remains reviewable.</p>
                <button className="button button-secondary" type="submit" disabled={!selectedCandidateId || busy === "profile"}>
                  {busy === "profile" ? "Saving…" : "Save search profile"}
                </button>
              </form>
            </details>
          </section>
        </aside>

        <section className="main-column">
          <section className="panel search-panel">
            <div className="panel-heading">
              <div><p className="section-kicker">03 / DISCOVERY</p><h2>Search opportunities</h2></div>
              <span className="result-count">{jobs?.total ?? 0} results</span>
            </div>
            <form className="job-search-form" onSubmit={searchJobs}>
              <label className="field search-query">
                <span>Role, company or keyword</span>
                <input value={jobQuery} onChange={(event) => setJobQuery(event.target.value)} placeholder="e.g. Python backend engineer" />
              </label>
              <label className="field">
                <span>Location</span>
                <input value={jobLocation} onChange={(event) => setJobLocation(event.target.value)} placeholder="Any location" />
              </label>
              <button className="button button-primary" type="submit" disabled={busy === "jobs"}>
                {busy === "jobs" ? "Searching…" : "Search jobs"}
              </button>
            </form>
          </section>

          <section className="panel results-panel">
            <div className="panel-heading">
              <div><p className="section-kicker">04 / MATCHING</p><h2>{matches ? "Your ranked matches" : "Available opportunities"}</h2></div>
              {selectedProfile && (
                <button className="button button-primary" type="button" onClick={evaluateMatches} disabled={busy === "matches"}>
                  {busy === "matches" ? "Evaluating…" : "Evaluate my matches"}
                </button>
              )}
            </div>

            {matches && (
              <div className="match-summary">
                <strong>{matches.evaluated_count} evaluated</strong>
                <span>{matches.total_jobs_available} open jobs available</span>
                {matches.truncated && <span className="warning-text">Evaluation capped at 500 recent jobs</span>}
                <button type="button" className="text-button" onClick={() => setMatches(null)}>Show all search results</button>
              </div>
            )}

            {matches ? (
              matches.items.length > 0 ? (
                <div className="job-list">
                  {matches.items.map(({ job, match }) => (
                    <article className="job-card" key={job.id}>
                      <div className="job-card-title">
                        <div><h3>{job.title}</h3><p>{job.company_name}</p></div>
                        <span className={`status-pill status-${match.status.replace("_", "-")}`}>
                          {match.status.replace("_", " ")}
                        </span>
                      </div>
                      <div className="job-meta">
                        <span>{job.location || "Location unknown"}</span>
                        <span>{job.work_mode || "Work mode unknown"}</span>
                        <span>{salaryLabel(job)}</span>
                      </div>
                      <div className="match-explanation">
                        <div className="score"><strong>{match.score.toFixed(1)}</strong><span>/ 100</span></div>
                        <div className="component-list">
                          {match.components.map((component) => (
                            <span key={component.name} title={component.explanation}>
                              {component.name.replace("_", " ")} {component.points.toFixed(1)}
                            </span>
                          ))}
                        </div>
                      </div>
                      {match.reasons.length > 0 && <p className="reason-line">{match.reasons.join(" · ")}</p>}
                      {match.unknown_fields.length > 0 && (
                        <p className="unknown-line">Needs review: {match.unknown_fields.join(", ")}</p>
                      )}
                      {job.canonical_url && (
                        <a className="job-link" href={job.canonical_url} target="_blank" rel="noreferrer">
                          Open original listing ↗
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state"><strong>No jobs to evaluate yet.</strong><span>Run discovery to add opportunities to your local workspace.</span></div>
              )
            ) : jobs?.items.length ? (
              <div className="job-list">
                {jobs.items.map((job) => (
                  <article className="job-card" key={job.id}>
                    <div className="job-card-title">
                      <div><h3>{job.title}</h3><p>{job.company_name}</p></div>
                      <span className="status-pill status-active">{job.status}</span>
                    </div>
                    <div className="job-meta">
                      <span>{job.location || "Location unknown"}</span>
                      <span>{job.work_mode || "Work mode unknown"}</span>
                      <span>{salaryLabel(job)}</span>
                    </div>
                    {job.canonical_url && (
                      <a className="job-link" href={job.canonical_url} target="_blank" rel="noreferrer">
                        Open original listing ↗
                      </a>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <strong>No indexed jobs yet.</strong>
                <span>Connect compliant sources and run discovery to populate this workspace.</span>
              </div>
            )}
          </section>
          <DiscoveryPanel onJobsRefresh={refreshJobs} />
          <ApplicationWorkflow
            candidate={selectedCandidate ?? null}
            jobs={jobs?.items ?? []}
            onCandidateUpdated={(updated) =>
              setCandidates((current) => current.map((item) => item.id === updated.id ? updated : item))
            }
          />
        </section>
      </div>

      <footer className="footer">
        <span>VacancyX · Local-first job discovery</span>
        <span>Recurring discovery requires the local scheduler and worker; browser assistance leaves final submission to you.</span>
      </footer>
    </main>
  );
}

export default App;
