# Module 23 — /v2 value endpoints + voice API (frontend contract completion)

Closes two blockers found by inspecting the actual route registrations
before any React Native / Antigravity frontend work could start:

- **Blocker A**: `/v2` (Module 19's session-authenticated multi-tenant
  surface) had auth but no product — every endpoint carrying real value
  (recommendation/irrigation/disease-risk/disease-risk-image/advisories/
  feedback) existed only under `/v1`'s single shared `FARMER_ID`.
- **Blocker B**: the voice stack (Module 12, containerized in Module 21)
  had no client-facing HTTP API at all — unreachable from outside the
  backend process.

See `decisions/0020-v2-value-endpoints-and-voice-api.md` for the full
reasoning and `CLAUDE.md`/`PROGRESS.md` for the module summary.
