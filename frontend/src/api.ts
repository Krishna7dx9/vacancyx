export type Candidate = {
  id: string;
  display_name: string;
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

  if (!response.ok) {
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
    throw new Error(message);
  }

  return (await response.json()) as T;
}
