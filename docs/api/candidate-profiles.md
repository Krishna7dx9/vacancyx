# Candidate profile API

Base path: /api/v1

The first profile API supports candidate profile creation, bounded listing, retrieval and partial updates.

| Method | Path | Behavior |
|---|---|---|
| POST | /candidates | Create a profile; returns 201 |
| GET | /candidates?limit=50&offset=0 | List active profiles; limit is 1–100 |
| GET | /candidates/{candidate_id} | Retrieve one profile |
| PATCH | /candidates/{candidate_id} | Update only supplied fields |

Request bodies are validated with strict Pydantic schemas; unknown fields are rejected. PATCH does not overwrite fields omitted from the body. A supplied null display name is invalid; optional contact/location values can be cleared with null. An empty PATCH is rejected. Missing IDs return 404.

Candidate records are configurable per local installation. No candidate name, contact detail, skills, education, experience or resume is embedded in application code. This API does not accept resume file bytes yet; secure upload and parsing are a later profile increment.

## Local-only security boundary

This API does not yet provide authentication or multi-user authorization. Keep the API bound to loopback (127.0.0.1) and do not expose it to a LAN, reverse proxy or public network. A later security milestone must add an explicit owner/session boundary and CSRF/Origin protections before remote access is supported.
