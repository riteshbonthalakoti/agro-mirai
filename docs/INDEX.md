# Documentation index

Where to find what, in this repo.

```
docs/
├── INDEX.md               # this file
├── NEXT_TEAM_HANDOVER.md  # production handover / ops runbook
├── architecture.md        # system architecture, component map, pipelines
├── ALGORITHMS.md          # what's learned vs. rule-based vs. an LLM call, and why
├── conventions.md         # units, timestamps, ID formats
├── testing-strategy.md    # test pyramid / CI gating strategy
├── TEST_CASES.md          # what the test suite actually checks
├── SMS_OTP_SETUP.md       # SMS Gateway + Android SMS Retriever setup
├── LOCAL_SETUP.md         # full local dev setup (backend, mobile, tests)
├── screenshots/           # app screenshots used in the README
└── images/                # logo animation and other graphics
```

## Core references

| Document | Covers |
|---|---|
| [architecture.md](architecture.md) | End-to-end component flow, external adapters, repository pattern, biological leaf gate, 3-tier voice fallback |
| [ALGORITHMS.md](ALGORITHMS.md) | Which parts are an LLM call, which are rule-based, which are a trained model — and the reasoning behind each choice |
| [NEXT_TEAM_HANDOVER.md](NEXT_TEAM_HANDOVER.md) | Production handover: build, deploy, admin access, operational runbook |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | Getting the backend, mobile app, and tests running on your own machine |
| [conventions.md](conventions.md) | Standard units (°C, mm, %), ISO 8601 UTC timestamps, entity ID formats |
| [testing-strategy.md](testing-strategy.md) | Unit / contract / edge-case / live-service test layering |
| [TEST_CASES.md](TEST_CASES.md) | What's actually covered by the 714-test suite, and what isn't |
| [SMS_OTP_SETUP.md](SMS_OTP_SETUP.md) | SMS relay delivery and Android SMS Retriever / User Consent auto-fill |
| [../specs/core/enums.md](../specs/core/enums.md) | Additive-only enum definitions, enforced by `tools/check_specs.py` in CI |
| [../specs/core/schema.yaml](../specs/core/schema.yaml) | Canonical entity schemas (Farmer, Field, SoilSample, WeatherReading, Advisory) |

## Architecture decisions

[`decisions/`](../decisions/) holds 31 ADRs — the actual reasoning behind the bigger calls, in order. Some worth knowing up front:

- [0015-et0-water-balance.md](../decisions/0015-et0-water-balance.md) — why irrigation advice is a physics-based water balance, not a trained classifier
- [0027-ecocrop-and-waterbalance-urgency.md](../decisions/0027-ecocrop-and-waterbalance-urgency.md) — why crop recommendation moved to FAO EcoCrop rules
- [0023-name-phone-otp-auth.md](../decisions/0023-name-phone-otp-auth.md) — why login is name + phone + OTP, no passwords
- [0026-three-microservices-render-split.md](../decisions/0026-three-microservices-render-split.md) — why inference and voice run as separate services from the main API
- [0031-free-tier-llm-cascade.md](../decisions/0031-free-tier-llm-cascade.md) — the key-pool rotation strategy behind every LLM call in the app

[0001-index.md](../decisions/0001-index.md) is the ADR directory's own index — numbering rules, status lifecycle, and the full list.

## Mobile app & distribution

The Android APK is served directly from `web/landing/app-release.apk` via the Vercel-hosted landing page (`agromirai.vercel.app/app-release.apk` and the `/download` page). It's a plain file in the repo, not a separate blob store — whatever's committed there is what ships.
