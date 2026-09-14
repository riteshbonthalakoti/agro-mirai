# MODULE 11 FIX-UP — add `/health` to the OpenAPI contract

Small, targeted fix before Module 13/14 start. Continuing in the
existing `agro-mirai` repo. Module 11 (API Layer) is done and committed
(`dac352c`) — this is a follow-up correction to it, not new scope.

## The gap

`src/agro_mirai/api/routes/health.py` implements `GET /health` and it's
tested and working. But it isn't in `specs/core/openapi.yaml` — the
Module 11 prompt required that any capability gap discovered during
implementation be added to `openapi.yaml` first, in its own commit, and
called out explicitly in the handoff as an additive change. That step
was missed; the handoff said "no gaps found," which wasn't accurate.
This isn't a functional bug (the endpoint works and is tested) — it's a
contract-discipline gap: `openapi.yaml` is supposed to be the source of
truth for every route that exists, and right now it's silently missing
one.

## Task

Add a `/health` path to `specs/core/openapi.yaml`, matching the style of
the existing paths (see `/farmers/me` as a template). It should be:
- `GET /health`
- No auth required (mark it explicitly not requiring `bearerAuth` —
  check how/whether other public endpoints in the spec, if any, express
  that; if none do, add `security: []` on this operation to override the
  global `bearerAuth` requirement)
- Response `200` with a small inline schema or a `HealthStatus` schema
  under `components/schemas` — whatever fits the existing schema style
  in this file — matching what `health.py` actually returns
  (`{"status": "ok" | "degraded"}`)

Confirm the implementation in `routes/health.py` matches whatever shape
you write into the spec (don't just write the spec to match the code
blindly — check both directions: if the code returns something the spec
can't cleanly describe, or vice versa, fix whichever side is wrong so
they agree).

Run `python tools/check_specs.py` and the API test suite
(`pytest tests/api/`) after the change to confirm nothing broke.

## Commit

One commit, its own: something like
`docs: add /health to openapi.yaml (contract gap from Module 11)`.
Push to `origin/main`.

## Handoff format

```
Module: 11 fix-up — /health added to openapi.yaml
Status: complete | blocked
Change made:
Files changed:
Commit made:
check_specs.py: pass/fail
API tests: <+pass/fail>
Next recommended module: 13 + 14 in parallel (M13: Feedback Loop, M14: Frontend)
```
