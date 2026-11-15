export type Candidate = {
  id: string;
  display_name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  skills: string[];
  is_active: boolean;
};

export type Job = {
  id: string;
  canonical_url: string | null;
  company_name: string;
  title: string;
  description: string | null;
  location: string | null;
  work_mode: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  status: string;
  last_verified_at: string | null;
};

export type JobSearchResponse = {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
};

export type MatchCriteria = {
  target_titles: string[];
  excluded_keywords: string[];
  required_skills: string[];
  allowed_locations: string[];
  work_modes: string[];
  employment_types: string[];
  minimum_salary?: number;
  salary_currency?: string;
};

export type SearchProfile = {
  id: string;
  candidate_id: string;
  name: string;
  criteria: MatchCriteria;
  is_enabled: boolean;
};

export type MatchComponent = {
  name: string;
  weight: number;
  raw_score: number;
  points: number;
  explanation: string;
  matched_terms: string[];
};

export type MatchResult = {
  status: "eligible" | "ineligible" | "needs_review";
  score: number;
  rule_version: string;
  reasons: string[];
  unknown_fields: string[];
  components: MatchComponent[];
};

export type SearchProfileMatchResponse = {
  profile_id: string;
  total_jobs_available: number;
  evaluated_count: number;
  truncated: boolean;
  items: { job: Job; match: MatchResult }[];
  limit: number;
  offset: number;
};

export type Resume = {
  id: string;
  candidate_id: string;
  original_filename: string;
  media_type: string;
  file_size_bytes: number;
  checksum_sha256: string;
  parse_status: "uploaded" | "parsed" | "reviewed" | "failed" | string;
  created_at: string;
  updated_at: string;
};

export type ResumeParseResult = {
  id: string;
  parse_status: string;
  parsed_content: {
    suggested_fields?: {
      emails?: string[];
      phone_numbers?: string[];
      urls?: string[];
    };
    reviewed_fields?: {
      display_name?: string;
      email?: string;
      phone?: string;
      location?: string;
      skills?: string[];
      links?: Record<string, string>;
    };
    warnings?: string[];
    extracted_text?: string;
  } | null;
};

export type CandidateAnswer = {
  id: string;
  candidate_id: string;
  question: string;
  answer_text: string;
  category: string | null;
  tags: string[];
  source: string;
  current_revision: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ApplicationSnapshot = {
  candidate: Record<string, unknown>;
  job: Record<string, unknown>;
  resume: { id: string; filename: string; checksum_sha256: string; parse_status: string } | null;
  answers: Array<{
    id: string;
    question: string;
    answer: string;
    category: string | null;
    tags: string[];
    revision: number;
    content_hash: string;
  }>;
  custom_fields: Record<string, string>;
  readiness: {
    status: "ready_for_review" | "needs_attention";
    missing_fields: string[];
    selected_answer_count: number;
  };
};

export type Application = {
  id: string;
  candidate_id: string;
  job_id: string;
  resume_id: string | null;
  status: string;
  current_revision: number;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  latest_revision: {
    id: string;
    revision: number;
    content_hash: string;
    content_snapshot: ApplicationSnapshot;
    resume_id: string | null;
    created_at: string;
  } | null;
};

async function readError(response: Response): Promise<string> {
  let message = `Request failed (${response.status})`;
  try {
    const payload: { detail?: unknown } = await response.json();
    if (typeof payload.detail === "string") {
      message = payload.detail;
    } else if (Array.isArray(payload.detail)) {
      message = payload.detail
        .map((item: { msg?: string }) => item.msg ?? "Invalid input")
        .join("; ");
    }
  } catch {
    // Keep the status-based message when the server response is not JSON.
  }
  return message;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as T;
}

export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/api/v1${path}`, { method: "POST", body });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as T;
}

export type ApplicationBatchItem = {
  id: string;
  application_id: string;
  revision: number;
  content_hash: string;
  decision: "pending" | "approved" | "rejected" | "stale";
  decided_at: string | null;
  current_revision: number;
  current_content_hash: string | null;
  is_stale: boolean;
  company_name: string;
  job_title: string;
  readiness_status: string | null;
  missing_fields: string[];
  content_snapshot: ApplicationSnapshot | null;
};

export type ApplicationBatch = {
  id: string;
  candidate_id: string;
  name: string;
  status: "reviewing" | "completed" | "cancelled";
  created_at: string;
  updated_at: string;
  items: ApplicationBatchItem[];
  total_items: number;
};

export type ApplicationBatchDecisionResult = {
  application_id: string;
  result: "approved" | "rejected" | "stale" | "needs_attention";
};

export type ApplicationBatchDecisionResponse = {
  batch: ApplicationBatch;
  results: ApplicationBatchDecisionResult[];
};


export type ApplicationStatusRead = {
  id: string;
  status: string;
  submitted_at: string | null;
};

export type ApplicationTimelineEvent = {
  id: string;
  event_type: string;
  occurred_at: string;
  metadata_json: Record<string, unknown>;
};

export type ApplicationTimelineEventType =
  | "assessment_scheduled"
  | "assessment_completed"
  | "interview_scheduled"
  | "interview_completed"
  | "offer_received"
  | "offer_declined"
  | "follow_up"
  | "note";


export type DiscoverySource = {
  source_key: string;
  company_name: string;
  provider: string;
};

export type DiscoveryTaskResult = {
  source_key?: string;
  status?: string;
  pages_fetched?: number;
  listings_seen?: number;
  jobs_created?: number;
  observations_created?: number;
  observations_updated?: number;
  truncated?: boolean;
  error_codes?: string[];
};

export type DiscoveryTask = {
  id: string;
  task_type: string;
  state: "queued" | "running" | "retry_wait" | "succeeded" | "partially_succeeded" | "failed" | "cancelled" | "needs_attention";
  attempts: number;
  max_attempts: number;
  available_at: string;
  lease_expires_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  result: DiscoveryTaskResult | null;
  created_at: string;
  updated_at: string;
};

export type DiscoveryTaskListResponse = {
  items: DiscoveryTask[];
  limit: number;
  offset: number;
};

export type DiscoveryTaskEnqueueResponse = {
  items: DiscoveryTask[];
};
