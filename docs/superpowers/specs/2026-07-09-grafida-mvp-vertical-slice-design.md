# Grafida MVP — Vertical Slice Design

**Date:** 2026-07-09
**Status:** Approved by product owner
**Context:** First implementation of the Greek legal AI SaaS blueprint. One complete
end-to-end flow, runnable locally, self-hosted AI (no external AI API dependency).

## Goal

A solo Greek lawyer can: log in → create a client and case → upload past documents
as style samples → upload new case facts/evidence → review AI-extracted facts →
generate a first draft of a court document in their own style → work through a
review checklist → approve with attestation → export to DOCX → find everything
again via search.

**Non-goal:** production readiness. This slice proves the pipeline and the product
shape. It must be honest everywhere (real extraction, real drafting, real gating),
thin everywhere (one flow, minimal polish).

## Locked decisions

| Decision | Choice |
|---|---|
| Scope | Vertical slice MVP (one end-to-end flow) |
| Stack | Next.js 15 (TS, Tailwind) frontend · FastAPI (Python 3.12, Docker) backend · Postgres + pgvector |
| AI | Self-hosted via Ollama on host (GPU-capable). Provider-agnostic interface. No external AI APIs. |
| Chat model | `ilsp/llama-krikri-8b` if pullable in Ollama, else `qwen2.5:7b`. Env-configurable (`AI_CHAT_MODEL`). |
| Embeddings | `bge-m3` via Ollama (`AI_EMBED_MODEL`). |
| Test AI | `MockProvider` implementing the same interface; deterministic outputs. |
| UI language | Greek |
| Seeded document type | Ανακοπή κατά διαταγής πληρωμής (mechanism generic; types are data) |

## Repository layout

```
lawyer/
├── docker-compose.yml          # postgres (pgvector image), backend, frontend
├── .env.example                # DB creds, JWT_SECRET, OLLAMA_BASE_URL, AI_* models
├── README.md                   # run instructions (Ollama native on Windows host)
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/                # migrations
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── auth/               # email+password, JWT, bcrypt
│       ├── models/             # SQLAlchemy entities
│       ├── api/                # routers: auth, clients, cases, documents,
│       │                       #   evidence, style, drafts, checklist, search, export
│       ├── files/              # local-disk storage (volume), text extraction
│       ├── ai/                 # provider interface, OllamaProvider, MockProvider
│       ├── agents/             # intake_extract, style_analyze, draft,
│       │                       #   consistency_check, checklist_build; pipeline runner
│       ├── search/             # hybrid: PG Greek FTS + pgvector, merged
│       └── export/             # python-docx DOCX generation
└── frontend/
    ├── Dockerfile
    └── src/app/                # login, dashboard, clients, cases/[id],
                                #   style, drafts/[id], search
```

## The flow (authoritative sequence)

1. **Login** — email + password (bcrypt), JWT in httpOnly cookie. Single user
   seeded via script; registration endpoint exists but unlinked in UI.
2. **Create client** — name, ΑΦΜ (optional), contact.
3. **Create case** — title, category, client, court (free text in slice),
   document-type selection from seeded types. Manual deadlines (date + title) only.
4. **Upload style samples** — DOCX/PDF per document type. Text extracted
   (python-docx / pypdf). Scanned PDFs (no text layer) are stored and flagged
   `ocr_pending`; excluded from style analysis. Minimum 3 samples to build a
   profile; UI shows n/10 progress and a quality warning below 10.
5. **Upload case facts/evidence** — files + free-text facts box. Each evidence
   file gets an exhibit number (σχετικό 1, 2, …).
6. **Extraction review** — `intake_extract` returns parties, dates, amounts,
   claims, each with `source_quote` and `confidence`. Never invents values;
   gaps are questions. Lawyer confirms/edits each field
   (`confirmed_by_lawyer` flips true). Confirmed record = the Case File.
7. **Generate draft** — `style_analyze` (if profile stale/missing) then `draft`:
   - Facts **only** from the Case File.
   - Style/structure from the StyleProfile + top-3 similar **scrubbed** exemplars
     (pgvector similarity over sample embeddings).
   - Legal references the model cannot ground are wrapped `[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ — δεν ανακτήθηκε πηγή]`.
   - Missing info renders as `[ΚΕΝΟ: …]`, never invented.
8. **Checklist** — `consistency_check` (draft vs Case File: names incl. Greek
   declension fuzzy match, dates, amounts, exhibit numbers) + `checklist_build`
   (merge findings + seeded per-doc-type standing items + fixed attestation item).
   Severities: red (blocking) / yellow (verify).
9. **Review & approve** — draft workspace: editable text (plain textarea/simple
   editor), checklist sidebar with jump-to-location. Red items must be resolved
   or overridden-with-note. Approve modal: attestation checkbox
   («Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος»). Approval recorded
   (user, timestamp, content hash) in AuditLog.
10. **Export DOCX** — python-docx; basic formatting (the lawyer's formatting
    fidelity is post-slice). **Server returns 403 unless the draft is approved.**
11. **Search** — one bar; hybrid keyword (PG `greek` text-search config) +
    semantic (pgvector cosine) over documents, samples, evidence text; results
    merged by reciprocal-rank fusion, grouped by type, with snippets. Scoped to
    the owning user in the SQL query itself.

## Data model (slice)

All tables carry `owner_user_id` (FK User) and timestamps. `firm_id` column
exists on User only, nullable, unused — schema headroom for multi-tenant later.

- **User:** email (unique), password_hash, full_name, firm_id (nullable).
- **Client:** name, afm, email, phone, notes.
- **Case:** client_id, title, category, court_name, status
  (`open/closed`), next_action, document ref numbers (free text).
- **Party:** case_id, name, role, source_quote, confirmed_by_lawyer.
- **CaseFact:** case_id, kind (`date/amount/claim/other`), value, description,
  source_quote, confidence, confirmed_by_lawyer, conflict_group (nullable —
  conflicting values share a group id and block drafting of affected sections).
- **Deadline:** case_id, title, due_date, confirmed (always true in slice —
  manual entry), completed_at.
- **DocumentType:** name_gr, category, checklist_template (JSON array of
  standing items). Seeded: Ανακοπή κατά διαταγής πληρωμής (+ generic type).
- **Document:** case_id, type_id, title, status (`draft/approved/exported`),
  current_version_id.
- **DocumentVersion:** document_id, version_no, content (text), author
  (`ai/lawyer`), content_hash.
- **Evidence:** case_id, exhibit_number, description, file_path, extracted_text,
  ocr_pending (bool).
- **StyleSample:** document_type_id, file_path, original_text, scrubbed_text,
  embedding (vector), status (`ok/ocr_pending/rejected`).
- **StyleProfile:** document_type_id, version, spec (JSON: structure[],
  phrase_bank{}, tone{}, formatting{}), built_from_sample_ids[],
  approved_by_lawyer.
- **AIDraft:** document_version_id, style_profile_id, inputs_manifest (JSON:
  case_file_hash, sample_ids, prompt_versions, model_id), uncertainty_report
  (JSON), status (`ok/failed`), error.
- **ChecklistItem:** document_id, source_agent, severity (`red/yellow`), text,
  anchor_quote, status (`open/resolved/overridden`), override_note, resolved_by.
- **AuditLog:** append-only — user_id, action, entity_type, entity_id,
  detail (JSON), created_at. Written for: login, uploads, extraction confirm,
  draft generation, checklist overrides, approval, export.

## AI layer

```python
class AIProvider(Protocol):
    def generate(self, *, system: str, user: str, json_schema: dict | None) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- **OllamaProvider** — HTTP to `OLLAMA_BASE_URL` (default
  `http://host.docker.internal:11434`), `/api/chat` + `/api/embed`,
  `format: json` when a schema is requested; retries ×2; hard timeout;
  failure surfaces as `AIDraft.status=failed` with a Greek error message —
  never a silent fallback.
- **MockProvider** — deterministic canned outputs keyed by prompt-template id;
  used in all pytest runs and when `AI_PROVIDER=mock`.
- Prompt templates live in versioned files (`app/agents/prompts/*.md`, Greek),
  ids recorded in `inputs_manifest`.

## Agents (sequential pipeline, not autonomous)

| Agent | Guarantee enforced in code (not just prompt) |
|---|---|
| `intake_extract` | Output validated against JSON schema; any field without a `source_quote` found verbatim (fuzzy ≥90%) in the source text is dropped to `null` + flagged. |
| `pii_scrub` (pre-style) | Regex + heuristics for Greek names (capitalized + declension endings), ΑΦΜ (9 digits), ΑΜΚΑ (11), amounts, dates, case numbers → typed placeholders. Runs before any style analysis; original text never enters style prompts. |
| `style_analyze` | Only patterns appearing in ≥2 samples enter the phrase bank; profile JSON schema-validated; stored with sample provenance. |
| `draft` | Post-generation scan: any 9/11-digit number or full name present in draft but absent from Case File → red checklist item (leak suspect). N-gram overlap (≥12-word verbatim spans vs samples, minus whitelisted legal formulas) → yellow item. |
| `consistency_check` | Names (Greek-declension-aware fuzzy), dates, amounts, exhibit numbers cross-checked draft ⇄ Case File; amounts/dates/names always red. |
| `checklist_build` | Merges agent findings + DocumentType.checklist_template + fixed attestation item; export gated server-side on all-red-resolved + attestation. |

Every step writes to `AIDraft.inputs_manifest` (model id, prompt version, input
hashes) — every draft is reproducible on paper.

## Frontend screens (Greek UI, Tailwind, function-first)

| Route | Content |
|---|---|
| `/login` | email/password |
| `/` | Dashboard: open cases, upcoming deadlines, drafts awaiting review |
| `/clients`, `/clients/[id]` | list + detail |
| `/cases`, `/cases/[id]` | list + detail tabs: Στοιχεία (case file fields + extraction review) / Έγγραφα / Σχετικά / Προσχέδια / Προθεσμίες |
| `/style` | per-doc-type sample upload (n/10 ring), profile view (structure, phrase bank with per-phrase delete, tone), rebuild button |
| `/drafts/[id]` | workspace: editor left, checklist right, transparency panel ("Τι χρησιμοποίησα"), approve modal with attestation |
| `/search` | one bar, grouped results with snippets |

## Security (slice level)

JWT (httpOnly, SameSite) · bcrypt · every query filtered by `owner_user_id`
server-side · uploads size/type-validated, stored outside webroot in a Docker
volume · AuditLog on all sensitive actions · export gate server-side ·
no external calls anywhere in the AI path.

## Testing

- **Backend (pytest, MockProvider):** extraction drops unquoted fields; scrubber
  removes seeded ΑΦΜ/names/amounts; draft leak-scan flags planted foreign name;
  export returns 403 before approval and 200 after; checklist override requires
  note; audit rows written; search scoping (user B cannot find user A's docs).
- **Frontend:** `next build` passes; one Playwright smoke (login → create case →
  see dashboard) if time permits, else manual script in README.
- **Real-model quality:** manual evaluation checklist in README (not CI).

## Explicitly out of scope

OCR · multi-user/firms/roles · billing · email/calendar/Viber alerts · external
legal research/databases · deadline computation (manual entry only) · procedure
playbooks beyond the one seeded checklist template · PDF export · formatting
fidelity to the lawyer's Word templates · MFA · mobile · deployment/hosting.

## Definition of done

`docker-compose up` + native Ollama ⇒ a user can complete the full flow of the
"authoritative sequence" above on a real Greek sample document set, and the
pytest suite passes with MockProvider.
