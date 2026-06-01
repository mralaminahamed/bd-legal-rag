# Security Policy

## Scope

BD Legal RAG is an operator-facing admin console that serves grounded answers about
Bangladeshi statute law. It is **not** a public-facing service in its default
configuration (`robots: noindex, nofollow`).

The security-critical surfaces are:

- **Admin API** (`/api/v1/admin/*`) — bearer-token authenticated; never expose without
  a strong token
- **Public query API** (`/api/v1/query*`) — rate-limited per hashed IP; no authentication
- **LLM prompt injection** — user input is fenced in delimited blocks, never concatenated
  into system instructions
- **Citation fabrication** — the citation validator strips any `{{cite:chunk_id}}`
  placeholder whose ID is not in the supplied chunk set; the LLM cannot cite sources it
  was not given

## What we consider a vulnerability

- Auth bypass on any `/api/v1/admin/*` endpoint
- Prompt injection that causes the system to emit legal conclusions in its own voice
  (bypassing the guardrails blacklist)
- Path traversal or SSRF via the bdlaws crawler or Ollama base URL
- SQL injection via any query parameter
- Disclosure of `admin_bearer_token`, API keys, or hashed IP values in logs or responses
- XSS in the React admin console
- Docker container escape or privilege escalation

## What is out of scope

- Rate-limiting bypass on the public query endpoint (it is intentionally lenient for
  local development; operators must configure stricter limits for production)
- The quality of legal information returned (this is an informational tool, not legal
  advice — see the disclaimer)
- Denial-of-service via large statutory documents (the chunker enforces a hard token cap)

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **mrabir.ahamed@gmail.com**

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (curl commands, payloads, screenshots)
- The version / commit hash you tested against

You will receive an acknowledgement within 48 hours. We aim to release a fix within
14 days for critical issues and 30 days for lower-severity findings.

We do not currently have a bug bounty programme.

## Security design notes

For context on the security decisions built into the system:

| Decision | Where |
|---|---|
| Admin bearer token guarding | `apps/api/app/api/deps.py` `require_admin` |
| Raw IPs never logged (SHA-256 hashed) | `apps/api/app/api/routes_query.py` `_ip_hash` |
| Prompt fencing (user input in delimited blocks) | `apps/api/app/prompts/families/legal_answer/v1.py` |
| Citation validator strips foreign placeholders | `apps/api/app/rag/citation.py` |
| Disclaimer injected application-side (LLM cannot suppress) | `apps/api/app/rag/generator.py` |
| Advice-seeking decline gate | `apps/api/app/rag/decline_gate.py` |
| Normative-conclusion blacklist | `apps/api/app/rag/guardrails.py` |
| Cost circuit breaker (prevents unbounded LLM spend) | `apps/api/app/llm/circuit_breaker.py` |

## Supported versions

Only the latest commit on the `main` branch receives security fixes. There are no
versioned release tracks at this time.
