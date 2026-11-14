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

## Resume metadata and upload

| Method | Path | Behavior |
|---|---|---|
| POST | /api/v1/candidates/{candidate_id}/resumes | Upload a validated PDF, DOCX or TXT file; returns 201 |
| GET | /api/v1/candidates/{candidate_id}/resumes | List safe metadata for the candidate's stored resumes |

The upload is streamed to a temporary file under the private local storage directory. Size is bounded by VACANCYX_MAX_RESUME_SIZE_BYTES (10 MiB by default). The server derives the media type from the extension and validates file signatures/content; the browser-supplied MIME type is not trusted. DOCX archives are bounded by entry count and uncompressed size, reject traversal paths/macros and are integrity-tested.

Stored files use server-generated UUID names under the private resumes directory. The original filename is reduced to a basename and sanitized. API responses never expose filesystem paths or storage keys. A SHA-256 checksum prevents storing identical resume bytes twice for the same candidate. New resumes begin with parse_status=pending; parsing and editable extraction are follow-on work.

## Local parsing and review

| Method | Path | Behavior |
|---|---|---|
| POST | /api/v1/resumes/{resume_id}/parse | Parse stored resume locally and save suggestions |
| GET | /api/v1/resumes/{resume_id}/parse | Read the latest extraction result |
| PATCH | /api/v1/resumes/{resume_id}/parse/review | Save user-confirmed field corrections |

PDF extraction is limited by configured page and character limits; encrypted PDFs are rejected. DOCX text is read from paragraphs and tables. TXT is decoded as UTF-8. Scanned PDFs are reported as having no selectable text; OCR is not enabled. No external AI or remote parser is called.

Raw extracted text and suggested fields remain separate from reviewed_fields. User edits never overwrite the source extraction. Parser output is a suggestion, not an automatic profile update; a later explicit user action must decide which reviewed values to apply to a candidate profile.
