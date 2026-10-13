# AGRO MIRAI — Complete Documentation Index

Welcome to the comprehensive documentation for **AGRO MIRAI**, the AI-driven agricultural advisory system for Indian farms.

---

## 1. Quick Navigation

| Section | Location | Description |
|---------|----------|-------------|
| **Core Architecture** | [`docs/architecture.md`](file:///c:/Projects/AGRO%20MIRAI/docs/architecture.md) | High-level data flow, repository patterns, and adapters |
| **Engineering Handover** | [`docs/NEXT_TEAM_HANDOVER.md`](file:///c:/Projects/AGRO%20MIRAI/docs/NEXT_TEAM_HANDOVER.md) | Up-to-date guide covering v2.2.2 production systems, APK release, and microservices |
| **Architecture Decision Records (ADRs)** | [`decisions/`](file:///c:/Projects/AGRO%20MIRAI/decisions/) | 30 formal records documenting every major architectural and technology choice |
| **Specifications & Contracts** | [`specs/core/`](file:///c:/Projects/AGRO%20MIRAI/specs/core/) | CI-enforced schema and enum contracts (`enums.md`, `schema.yaml`) |
| **Research & Farmer UX** | [`docs/research/`](file:///c:/Projects/AGRO%20MIRAI/docs/research/) | Field research on Indian smallholders, model comparisons, and UX audits |
| **Model Evaluations** | [`docs/eval/`](file:///c:/Projects/AGRO%20MIRAI/docs/eval/) | Benchmark metrics for crop models, disease CNN, and irrigation advisory |
| **Authentication & Accounts** | [`docs/ACCOUNTS.md`](file:///c:/Projects/AGRO%20MIRAI/docs/ACCOUNTS.md) & [`docs/SMS_OTP_SETUP.md`](file:///c:/Projects/AGRO%20MIRAI/docs/SMS_OTP_SETUP.md) | Name + Phone + OTP authentication, multi-account switching, and SMS retriever |
| **Mobile & Notifications** | [`docs/MODULE_53_NOTIFICATIONS.md`](file:///c:/Projects/AGRO%20MIRAI/docs/MODULE_53_NOTIFICATIONS.md) | Per-account notifications, daily reminder scheduling, and slide-up drawer |
| **Testing Strategy** | [`docs/testing-strategy.md`](file:///c:/Projects/AGRO%20MIRAI/docs/testing-strategy.md) | Unit, integration, and CI regression testing suite |
| **Deployment Runbooks** | [`docs/deploy/`](file:///c:/Projects/AGRO%20MIRAI/docs/deploy/) | Infrastructure setup guides for Render, Vercel, Supabase, and Oracle Cloud |

---

## 2. Architecture Decision Records (ADRs)

The [`decisions/`](file:///c:/Projects/AGRO%20MIRAI/decisions/) directory contains 30 Architectural Decision Records (ADRs) documenting every key design choice:

- **0001–0006**: [Foundation, ID formats, tenancy, GEE fallback, migrations, and missing data policies](file:///c:/Projects/AGRO%20MIRAI/decisions/0001-index.md)
- **0007–0012**: Feature mapping, disease models, SHAP explainability, decision engine, and feedback loops
- **0013–0016**: Frontend sequencing, deployment targets, ET0 water balance (FAO-56), and regional crop suitability
- **0017–0020**: Multi-tenant v2 auth, PlantVillage MobileNetV2 CNN, deployment topology, and v2 REST APIs
- **0021–0024**: Regional languages (Kannada/Telugu/Hindi), Supabase Auth migration, OTP login, and multilingual i18n
- **0025–0030**: ONNX inference microservices, Render microservices split, EcoCrop + FAO-56 balance, PlantDoc dataset, and admin dashboard write actions

---

## 3. Current Release (v2.2.2 Production)

- **Universal Release APK**: `https://agromirai.vercel.app/app-release.apk`
- **Web Download Portal**: `https://agromirai.vercel.app/download`
- **Key Enhancements**:
  - Direct Vercel Edge CDN distribution with `no-transform` header preventing mobile browser download stalls.
  - Native SMS Retriever API auto-fill for 6-digit OTPs without manual typing.
  - Dual-layer biological leaf validation gate (`leaf_gate.py`) rejecting non-foliage images.
  - Interactive MapLibre GL field map with live phone GPS auto-tracking beacon.
  - Farmer-centric weekly summary cards and agronomic timeline in `DataTab.tsx`.
  - Full migration to `lucide-react-native` vector icons and animated notification drawer.
