# Software Requirements Specification

**Project:** Bangladesh Legal RAG (`bd-legal-rag`)
**Author:** Al Amin Ahamed ([@mralaminahamed](https://github.com/mralaminahamed))
**Document version:** 1.0
**Status:** Approved for implementation
**Last updated:** May 2026

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for **Bangladesh Legal RAG**, a Retrieval-Augmented Generation system that answers questions about Bangladeshi statute law, grounded in the official corpus at `bdlaws.minlaw.gov.bd`. The system is intended for lawyers, compliance officers, SME founders, and researchers who need to locate the applicable section of an Act and read it in plain language without expensive legal consultation for first-pass research.

This SRS is the authoritative reference for the architecture, implementation plan, and Claude Code prompt sequence that accompany it. It is written for a development team and is suitable for direct hand-off.

The system is an **informational research tool, not a substitute for legal advice**. This constraint is treated as a first-class non-functional requirement that shapes generation, the user interface, and the eval suite.

### 1.2 Scope

The system ingests Acts from `bdlaws.minlaw.gov.bd` in their Bengali (authoritative) and English (translated) forms, preserves the statutory hierarchy (Act → Part → Chapter → Section → Subsection → Clause), embeds sections with a multilingual model, and serves grounded answers through a FastAPI service consumed by a search-style web interface.

**In scope (v1.0):**

- Ingestion of five Acts as the foundational corpus: Companies Act 1994, Income Tax Act 2023, Value Added Tax and Supplementary Duty Act 2012, Bangladesh Labour Act 2006, and Digital Security Act 2018.
- Bilingual storage and retrieval: Bengali (authoritative) and English (reference translation), with explicit marking of language and translation status on every chunk.
- Section-hierarchy-aware chunking that preserves the statutory tree on every chunk.
- Multilingual embedding (`embed-multilingual-v3.0`) and hybrid retrieval with a mandatory cross-encoder rerank.
- Canonical legal citation formatting on every answer (`Section X(Y)(Z) of Act <name>, <year>`).
- Multi-provider grounded generation with mandatory disclaimer injection, confidence tiering, and a decline path for queries seeking legal advice.
- Effective-date awareness: the corpus records when a provision is in force and surfaces the version applicable on a user-supplied "as of" date.
- A versioned prompt registry and a CI-gated eval suite tailored to legal-domain metrics (section citation accuracy, language routing accuracy, decline accuracy).
- A bilingual search-style web interface.

**Out of scope (v1.0):**

- Case law and judicial decisions (Supreme Court / High Court judgments). The corpus is statutes only. Deferred to v1.1.
- Subsidiary legislation (SROs, Gazette notifications) beyond what is published on `bdlaws`. Deferred to v1.2.
- Cross-jurisdictional comparison with foreign law.
- Automated drafting of legal documents (contracts, notices). The system answers questions; it does not generate legal instruments.
- Per-user accounts, saved searches, or annotation. The v1.0 interface is anonymous.

### 1.3 Definitions and Acronyms

| Term | Definition |
|---|---|
| Act | A statute enacted by Parliament, identified by name, number, and year (e.g. Act XVIII of 1994). |
| Section | The smallest formally numbered unit of an Act; the natural unit of retrieval. |
| Statutory hierarchy | Act → Part → Chapter → Section → Subsection → Clause; preserved on every chunk. |
| Amendment | A subsequent Act that modifies or repeals provisions of an earlier Act. |
| Effective date | The date on which a provision came into force; may be conditional on a Gazette notification. |
| Authoritative version | The Bengali original. The English translation is reference only and may lag amendments. |
| Citation | A canonical reference: `Section X(Y)(Z) of <Act Name>, <Year>` (English) / `<আইনের নাম>, <বছর>-এর ধারা X(Y)(Z)` (Bengali). |
| Decline path | Refusal to answer when the query seeks legal advice or falls outside the corpus. |
| Disclaimer | Mandatory notice in every response that this is informational, not legal advice. |
| RAG | Retrieval-Augmented Generation. |
| HNSW | Hierarchical Navigable Small World — pgvector's ANN index. |

### 1.4 References

- `bdlaws.minlaw.gov.bd` — Bangladesh Ministry of Law, Justice and Parliamentary Affairs official statute portal.
- Prior section-scoped chunking work — *"How I Cut Edit Distance from 168 to 43 in a Legal Document RAG Pipeline"* (author's blog).
- Cohere `embed-multilingual-v3.0` documentation.
- Cohere `rerank-multilingual-v3.0` documentation.

---

## 2. Overall Description

### 2.1 Product Perspective

The product is a standalone, self-hosted service. It does not modify the source portal in any way; it consumes the public corpus and indexes it locally. The author operates the deployment on Hetzner. Operational simplicity, low fixed cost, and clear citation behaviour are first-class concerns because the credibility of the tool rests on traceability to the official source.

### 2.2 Product Functions (summary)

1. Crawl and ingest the five foundational Acts in Bengali and English.
2. Preserve the statutory hierarchy on every chunk and record effective dates.
3. Detect the language of an incoming query and route retrieval accordingly.
4. Retrieve the most relevant sections using hybrid search with mandatory reranking.
5. Generate a grounded answer with canonical citation, plain-language summary, confidence tier, and mandatory disclaimer.
6. Decline to answer queries that seek legal advice or fall outside the corpus.
7. Capture feedback and emit quality, cost, and decline metrics.
8. Evaluate against a fixed bilingual golden dataset on every prompt or retrieval change.

### 2.3 User Classes and Characteristics

| User class | Description | Primary interactions |
|---|---|---|
| **Researcher / SME founder** | Non-lawyer seeking to locate the applicable provision. | Search interface; reads cited section + plain-language summary. |
| **Lawyer / compliance officer** | Domain expert using the tool for first-pass research. | Search with explicit Act/section filters; cross-references the original Bengali text. |
| **Operator** | The author — corpus curation, ingestion, monitoring. | Admin API, metrics, eval reports. |
| **CI system** | GitHub Actions running quality gates and eval. | Eval harness, structured outputs. |

### 2.4 Operating Environment

- **Runtime:** Python 3.12+, asyncio throughout.
- **Datastore:** PostgreSQL 16 with pgvector (≥ 0.6.0; HNSW on `vector(1024)`).
- **Cache / broker:** Redis 7.
- **Background processing:** Celery + Celery beat.
- **Deployment:** Docker Compose on a single Hetzner host behind Caddy with automatic TLS.
- **External services:** Cohere Embed Multilingual and Rerank Multilingual APIs, Anthropic Messages API, OpenAI API (alternate provider), optional local Ollama, and the `bdlaws.minlaw.gov.bd` portal.

### 2.5 Design and Implementation Constraints

- Python 3.12+ with full type annotations; `mypy --strict` must pass.
- `async`/`await` throughout; no synchronous blocking in async contexts.
- FastAPI with Pydantic v2 request/response models and validation.
- SQLAlchemy 2.0 async with connection pooling.
- Every LLM and embedding call carries an explicit timeout, bounded retry with exponential backoff, and structured error handling.
- Prompts are versioned code in a registry with changelogs.
- All generation paths must inject the legal disclaimer and apply the no-legal-advice guardrail; no configuration toggle weakens or removes the disclaimer.
- Citations rendered to users must be canonical and must reference only sections actually retrieved.
- Authorship in code comments and documentation references Al Amin Ahamed personally.
- The system never asserts a legal conclusion in its own voice; it summarises and cites.

### 2.6 Assumptions and Dependencies

- `bdlaws.minlaw.gov.bd` remains publicly accessible under polite crawling and its HTML structure remains broadly stable.
- The author holds valid Cohere and Anthropic credentials.
- pgvector ≥ 0.6.0 is available on the target Postgres image (the chosen embedding dimension 1024 fits within the standard HNSW limit).
- For the five foundational Acts, both Bengali and English versions exist on the portal; for Acts where only Bengali is available, the system records and exposes that asymmetry.

---

## 3. Functional Requirements

Requirements are identified as `FR-<area>-<n>` with priority **MUST**, **SHOULD**, or **MAY**.

### 3.1 Corpus and Source Management

| ID | Priority | Requirement |
|---|---|---|
| FR-CM-1 | MUST | The system shall represent each Act with a stable identity: short name, full name, Act number, year, ministry, and current status (`in_force`, `partially_repealed`, `repealed`). |
| FR-CM-2 | MUST | The system shall record every revision of a provision with `effective_from` and optional `effective_to` dates and a link to the amending Act. |
| FR-CM-3 | MUST | The system shall mark each chunk with `language` (`bn` or `en`) and `translation_status` (`authoritative`, `reference_translation`). |
| FR-CM-4 | MUST | The system shall support adding further Acts beyond the v1.0 five through declarative configuration without code changes. |
| FR-CM-5 | SHOULD | The system shall record an `as_of` field per provision indicating the date the snapshot was taken from the portal. |

### 3.2 Ingestion

| ID | Priority | Requirement |
|---|---|---|
| FR-IN-1 | MUST | The system shall crawl `bdlaws.minlaw.gov.bd` for the configured Acts, fetching both Bengali and English versions where available. |
| FR-IN-2 | MUST | The crawler shall observe a configured request rate ceiling and honour `Retry-After`. |
| FR-IN-3 | MUST | The crawler shall extract the statutory hierarchy (Act → Part → Chapter → Section → Subsection → Clause) from page structure into a typed parse tree. |
| FR-IN-4 | MUST | The system shall compute a `content_hash` per section and skip re-embedding when the hash is unchanged. |
| FR-IN-5 | MUST | Ingestion shall run as Celery tasks; one task per `(act, language)` pair; failure in one pair shall not abort others. |
| FR-IN-6 | SHOULD | The system shall detect and record amendments where the source page indicates them, populating `effective_from`/`effective_to`. |
| FR-IN-7 | SHOULD | The crawler shall preserve the original HTML alongside the normalised text for audit purposes. |

### 3.3 Processing and Indexing

| ID | Priority | Requirement |
|---|---|---|
| FR-PR-1 | MUST | The system shall chunk Acts using a section-hierarchy-aware strategy: one chunk per leaf provision (subsection or clause where present, otherwise section), with paragraph-level fallback for oversized provisions. |
| FR-PR-2 | MUST | Every chunk shall carry: `act_id`, `act_name`, `act_year`, `part`, `chapter`, `section`, `subsection`, `clause`, `language`, `translation_status`, `effective_from`, `effective_to`, and `source_url`. |
| FR-PR-3 | MUST | The system shall embed chunks with `embed-multilingual-v3.0` using `input_type=search_document`, batched at the model's documented batch ceiling. |
| FR-PR-4 | MUST | The system shall persist chunk embeddings as `vector(1024)` with an HNSW cosine index. |
| FR-PR-5 | MUST | The system shall maintain a lexical index (`tsvector` with the simple configuration for Bengali tolerance) on chunk content for hybrid retrieval. |
| FR-PR-6 | SHOULD | The system shall maintain per-Act centroid embeddings in Redis for routing. |

### 3.4 Query, Routing, and Retrieval

| ID | Priority | Requirement |
|---|---|---|
| FR-QR-1 | MUST | The system shall accept a free-text question with optional filters: `act_slug`, `language` (`bn`/`en`/`auto`), `as_of_date`. |
| FR-QR-2 | MUST | When `language=auto`, the system shall detect the query language from script (Bengali Unicode block vs Latin) with a fallback heuristic for mixed-script queries. |
| FR-QR-3 | MUST | The system shall retrieve from the language-matching index by default and shall additionally retrieve from the opposite-language index when retrieval recall is below a configured threshold (cross-lingual fallback). |
| FR-QR-4 | MUST | The system shall perform hybrid retrieval using vector cosine (HNSW, with `input_type=search_query`) and lexical search, merged via Reciprocal Rank Fusion. |
| FR-QR-5 | MUST | The system shall apply a **mandatory** cross-encoder rerank (`rerank-multilingual-v3.0`) over the fused candidate set. Reranking is not optional in this system. |
| FR-QR-6 | MUST | When `as_of_date` is supplied, the system shall filter retrieved chunks to those whose `effective_from ≤ as_of_date` and (`effective_to IS NULL` or `effective_to ≥ as_of_date`). |
| FR-QR-7 | SHOULD | The system shall expose a faceted browse mode allowing direct navigation by Act → Chapter → Section without a query. |

### 3.5 Generation, Citation, and Safety

| ID | Priority | Requirement |
|---|---|---|
| FR-GN-1 | MUST | Every answer shall include: (a) a plain-language summary, (b) the verbatim text of the cited provision(s), (c) canonical citation(s), (d) a confidence tier, and (e) the legal disclaimer. |
| FR-GN-2 | MUST | The system shall render citations canonically: English form `Section X(Y)(Z) of <Act Name>, <Year>`; Bengali form `<আইনের নাম>, <বছর>-এর ধারা X(Y)(Z)`. |
| FR-GN-3 | MUST | The system shall cite only chunks that were supplied to the model. Any citation the model produces that does not match a supplied chunk shall be stripped. |
| FR-GN-4 | MUST | The system shall compute a confidence tier (`HIGH`, `MEDIUM`, `LOW`) from rerank score distribution, retrieval recall, and language coverage. The user shall see the tier. |
| FR-GN-5 | MUST | The system shall **never** state a legal conclusion in its own voice (e.g. "you must…", "this is illegal…"). It shall attribute every normative statement to the cited provision. |
| FR-GN-6 | MUST | The system shall take the decline path when (a) the query seeks legal advice ("should I…", "what should I do if…", "is it legal for me to…") or (b) retrieval recall is below the configured floor. The decline message shall direct the user to consult a qualified legal practitioner. |
| FR-GN-7 | MUST | The legal disclaimer shall be injected by the generator and not by the LLM; the model cannot omit, summarise, or alter it. |
| FR-GN-8 | MUST | The system shall route generation through a provider-agnostic interface supporting Claude, OpenAI, and Ollama. |
| FR-GN-9 | MUST | The system shall cache responses in Redis keyed on a hash of normalised query + retrieved-chunk fingerprint + `as_of_date` + model + prompt version. |
| FR-GN-10 | MUST | The system shall apply a per-request cost circuit breaker. |
| FR-GN-11 | MUST | On LLM provider failure, the system shall fail open and return the retrieved provisions with citations and disclaimer; it shall not synthesise a summary. |
| FR-GN-12 | SHOULD | When the query is in one language and the authoritative chunk is in the other, the response shall surface both texts side by side and mark which is authoritative. |

### 3.6 Feedback and Metrics

| ID | Priority | Requirement |
|---|---|---|
| FR-FB-1 | MUST | The system shall log each query: detected/selected language, retrieval set, rerank scores, response, confidence tier, declined flag, cost, latency, and cache-hit. |
| FR-FB-2 | MUST | The system shall accept user feedback (`helpful`, `not_helpful`, `wrong_citation`, `out_of_scope`) bound to a query. |
| FR-FB-3 | SHOULD | The system shall expose metrics: decline rate, mean confidence by category, citation-accuracy by Act, p95 latency, cache-hit rate, and daily spend. |
| FR-FB-4 | MAY | The system shall surface the most-frequent `wrong_citation` patterns to guide reranker tuning. |

### 3.7 Evaluation

| ID | Priority | Requirement |
|---|---|---|
| FR-EV-1 | MUST | The system shall provide an eval harness that runs a fixed bilingual golden dataset through the full retrieval and generation path with all external calls mocked or VCR-replayed. |
| FR-EV-2 | MUST | The harness shall compute: section citation accuracy (top-1 exact section match), context recall (any chunk from the expected section in top-k), language routing accuracy, decline accuracy (on advice-seeking and out-of-scope queries), and answer edit distance against reference summaries. |
| FR-EV-3 | MUST | Any change to a prompt, the chunker, the embedder, the reranker, or the language router shall require a passing eval run before merge. |
| FR-EV-4 | MUST | The dataset shall include at least 60 records spanning all five Acts in both Bengali and English, with at least 10 advice-seeking records (decline path) and at least 10 out-of-scope records. |
| FR-EV-5 | SHOULD | The harness shall produce a per-Act and per-language breakdown so regressions in one slice are visible. |

### 3.8 Delivery (Interface and API)

| ID | Priority | Requirement |
|---|---|---|
| FR-DL-1 | MUST | The system shall expose a public query endpoint with per-IP rate limiting. |
| FR-DL-2 | MUST | The system shall ship a bilingual web interface (Bengali / English UI strings) with a search box, filters (Act, language, `as_of_date`), and a result view that presents the citation, plain-language summary, verbatim provision, confidence tier, and disclaimer. |
| FR-DL-3 | SHOULD | The interface shall offer a faceted browse mode (Act → Chapter → Section) independent of search. |
| FR-DL-4 | MUST | Admin endpoints (ingestion trigger, metrics, corpus curation) shall require bearer-token authentication. |
| FR-DL-5 | MUST | The system shall expose a `/health` endpoint reporting database, Redis, Cohere, and provider reachability. |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement |
|---|---|
| NFR-PF-1 | End-to-end query latency (cache miss, single Act, with rerank) shall be ≤ 5 s at p95 under nominal load. |
| NFR-PF-2 | Cache-hit query latency shall be ≤ 250 ms at p95. |
| NFR-PF-3 | pgvector retrieval shall use HNSW; an exact sequential scan in the hot path is prohibited. |
| NFR-PF-4 | Embedding and rerank calls shall be batched per the provider's documented limits. |
| NFR-PF-5 | Database access shall use an async pool; per-request connection open/close is prohibited. |
| NFR-PF-6 | Ingestion and embedding shall run as Celery jobs; the HTTP request path shall never block on either. |

### 4.2 Reliability and Availability

| ID | Requirement |
|---|---|
| NFR-RL-1 | The retrieval path shall remain available when any single LLM provider is unreachable (fail-open returns retrieved provisions, citations, and disclaimer). |
| NFR-RL-2 | When the reranker is unreachable, the system shall surface a `LOW` confidence tier and proceed with the fused candidates rather than failing the request. |
| NFR-RL-3 | A failed ingestion run shall be retryable and idempotent; partial runs shall not corrupt the index. |
| NFR-RL-4 | The cost circuit breaker shall guarantee no single query exceeds the configured ceiling. |

### 4.3 Legal-Domain Safety (first-class)

| ID | Requirement |
|---|---|
| NFR-LS-1 | Every response visible to a user — including cache-hits, fail-open responses, decline responses, and error responses — shall carry the legal disclaimer. The disclaimer is appended by the application, not authored by the LLM. |
| NFR-LS-2 | The system shall not state a normative legal conclusion in its own voice. Generation tests shall enforce this against an explicit phrase blacklist (e.g. "you must", "you cannot", "it is illegal", in both English and Bengali). |
| NFR-LS-3 | When the query is advice-seeking, the system shall take the decline path even when retrieval returns relevant chunks. |
| NFR-LS-4 | When only an unofficial English translation is available for a provision, the response shall mark the translation as reference and direct the user to the Bengali authoritative text. |
| NFR-LS-5 | The disclaimer text and decline text shall be reviewable, version-controlled artifacts under `app/prompts/safety/`. |

### 4.4 Security

| ID | Requirement |
|---|---|
| NFR-SC-1 | API credentials shall be environment-only, never committed, and never logged. |
| NFR-SC-2 | Admin endpoints shall require a bearer token; public endpoints shall be rate-limited per hashed IP in Redis. |
| NFR-SC-3 | User-supplied query text shall be length-bounded and fenced in non-instructional blocks in the prompt; retrieved content shall be similarly fenced. |
| NFR-SC-4 | Ingested HTML shall be sanitised before storage; the preserved original HTML (FR-IN-7) shall be stored separately and never injected into prompts. |
| NFR-SC-5 | The query log shall record only a truncated hash of the user IP. |

### 4.5 Maintainability and Quality

| ID | Requirement |
|---|---|
| NFR-MN-1 | `mypy --strict` shall pass as a CI gate. |
| NFR-MN-2 | `ruff` (lint + format + imports) shall pass as a CI gate. |
| NFR-MN-3 | `pytest` with `pytest-asyncio` shall pass; all external calls mocked or VCR-replayed. |
| NFR-MN-4 | Provider selection, chunking parameters, retrieval weights, decline thresholds, and disclaimer text shall be configuration-driven. |
| NFR-MN-5 | All public functions and classes shall carry Google-style docstrings. |

### 4.6 Portability

| ID | Requirement |
|---|---|
| NFR-PT-1 | The system shall run from `docker compose up` with no host dependencies beyond Docker. |
| NFR-PT-2 | Embeddings use `vector(1024)` with HNSW, which fits comfortably within pgvector's standard limits; no `halfvec` fallback is required. |

### 4.7 Observability

| ID | Requirement |
|---|---|
| NFR-OB-1 | Every request shall emit structured logs with a correlation id, detected language, Act slug(s) retrieved, confidence tier, decline flag, latency, tokens, and cost. |
| NFR-OB-2 | Eval results shall be persisted with the prompt version, retrieval config, and rerank config that produced them. |
| NFR-OB-3 | The disclaimer text version that accompanied each response shall be recorded with the query. |

---

## 5. Acceptance Criteria

The release is accepted when all of the following hold:

1. All **MUST** functional requirements are implemented and exercised by tests.
2. CI gates pass: `ruff`, `mypy --strict`, `pytest`, and the eval suite.
3. The golden eval reports section citation accuracy ≥ 0.85, language routing accuracy ≥ 0.95, and decline accuracy ≥ 0.95 on the committed dataset.
4. A live demonstration over 30 mixed Bengali/English research questions returns the correct section in the top-1 citation in at least 80% of cases (operator-judged against the Act portal).
5. The bilingual web interface returns a cited answer with disclaimer for a registered Act in both Bengali and English.
6. Killing the LLM provider mid-session demonstrates fail-open: the user still receives the retrieved provisions, canonical citations, and disclaimer.
7. Killing the reranker demonstrates degraded-confidence behaviour: the system still answers but marks confidence as `LOW`.
8. An advice-seeking query ("Should I sue my employer for unpaid wages?") takes the decline path and directs the user to a legal practitioner.
9. The disclaimer is present on every response observed during the acceptance demo, including cache-hits and errors.

---

## 6. Golden Evaluation Dataset (specification)

The eval dataset is a fixed JSONL file committed to the repository. Each record:

```json
{
  "id": "labour-2006-bn-014",
  "language": "bn",
  "act_slug": "labour-act-2006",
  "question": "শ্রমিকের সাপ্তাহিক ছুটি কত দিন?",
  "expected_act": "Bangladesh Labour Act, 2006",
  "expected_section": "103",
  "expected_subsection": null,
  "reference_summary": "প্রত্যেক শ্রমিক প্রতি সপ্তাহে এক দিন পূর্ণ বেতনে ছুটি পাওয়ার অধিকারী।",
  "must_cite": true,
  "category": "factual",
  "should_decline": false
}
```

Coverage requirements:

- **≥ 60 records** spanning the five v1.0 Acts.
- **Both languages** represented across every Act (at least 4 BN + 4 EN per Act).
- **Categories**: `factual` (the answer is a single section), `multi-section` (the answer spans two or more sections), `temporal` (requires `as_of_date` filtering), `advice_seeking` (must decline), `out_of_scope` (must decline).
- **≥ 10 records** in `advice_seeking`, **≥ 10 records** in `out_of_scope`.

---

## 7. Disclaimer Text (initial, version-controlled in `app/prompts/safety/`)

> **English (v1)**: This response is generated by an automated research assistant grounded in the publicly published text of Bangladeshi statutes. It is informational and is not legal advice, does not establish an attorney-client relationship, and may not reflect the most current amendments. For decisions affecting your rights or obligations, consult a qualified legal practitioner enrolled with the Bangladesh Bar Council.
>
> **Bengali (v1)**: এই উত্তরটি বাংলাদেশের প্রকাশিত আইনের ভিত্তিতে একটি স্বয়ংক্রিয় গবেষণা সহায়ক দ্বারা তৈরি। এটি কেবল তথ্যমূলক, আইনি পরামর্শ নয়, এবং এটি কোনো আইনজীবী-মক্কেল সম্পর্ক স্থাপন করে না। সাম্প্রতিক সংশোধনী এতে নাও থাকতে পারে। আপনার অধিকার বা দায়বদ্ধতা সংক্রান্ত সিদ্ধান্তের জন্য বাংলাদেশ বার কাউন্সিলে নিবন্ধিত যোগ্য আইনজীবীর পরামর্শ নিন।

The disclaimer is appended by `app/rag/generator.py`. It is never inside the model's context window as instructions, only ever surrounding the model's output as application-controlled text.

---

## 8. Traceability Summary

| Requirement group | Architecture component | Implementation phase |
|---|---|---|
| FR-CM-* | Corpus registry, data model | Phase 1 |
| FR-IN-* | bdlaws crawler, Celery tasks | Phase 2 |
| FR-PR-* | Section-aware chunker, multilingual embedder | Phase 3 |
| FR-QR-* | Language router, hybrid retriever, mandatory reranker | Phase 4 |
| FR-GN-*, NFR-LS-* | LLM driver, prompt registry, citation formatter, disclaimer injector, decline gate | Phase 5 |
| FR-FB-*, FR-DL-* | FastAPI service, bilingual web interface | Phase 6 |
| FR-EV-* | Eval harness with legal-domain metrics, CI gate | Phase 7 |
| NFR-* (deploy) | Docker Compose, Caddy, CI/CD | Phase 0, Phase 8 |

---

*Authored by Al Amin Ahamed. This SRS governs the accompanying Architecture, Implementation Plan, Claude Code prompts, and CLAUDE.md files.*
