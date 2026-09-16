# MODULE 30 — Investigate real-time conversational voice AI (stop-and-report, no build yet), plus verify Module 28/29's fixes live

Continuing AGRO MIRAI. This is a **research-and-report module, like Module
26's "stop and report before executing" pattern** — do not integrate any
voice API, do not touch `mobile/App.tsx`'s voice code, and do not write a
production prompt for this yourself. The point is to come back with real,
verified findings so Ritesh can make an informed decision, the same way
Module 26 stopped before touching auth.

## Why this is a stop-and-report module, not a build module

Ritesh wants farmers to be able to talk to AGRO MIRAI in real time —
ask a question by voice, get a spoken answer back — using a free-tier
API, replacing today's mocked/pre-scripted voice playback. The trap:
every well-known "free tier real-time voice" product (OpenAI Realtime
API, Google Gemini Live API, and similar) is built API-first for
English and a handful of major world languages. This project's whole
voice stack exists — AI4Bharat, IndicTrans2, IndicConformer, vits_rasa_13
— specifically *because* generic voice APIs don't reliably cover
Kannada, Telugu, and Hindi at production quality. Picking a "free"
realtime API without checking its actual Indian-language coverage would
repeat exactly the kind of silently-wrong assumption Module 26 avoided
by stopping to ask first — so stop and ask first here too.

## Part 1 — Verify Module 28/29's fixes are actually live (do this first, it's fast)

Before researching anything new, confirm the ground truth of what's
already supposedly fixed, since recent reports have not always held up
under a fresh test:

1. Run `npx expo start -c`, fully restart Expo Go on the phone, and try
   a real leaf scan. Paste the actual Metro log. Confirm: a genuine `200`
   with a real model response, not the old `Unsupported FormDataPart
   implementation` error and not any fabricated "local AI model result."
2. Switch the language picker on a real device and confirm real UI text
   changes on at least two screens (Home and one detail screen) — paste
   before/after screenshots, not a description.
3. Report both results honestly, including if either is still broken.
   Do not report "complete" without the actual evidence attached — this
   is the same bar every module in this project has been held to.

## Part 2 — Research real-time conversational voice AI, Indian-language-first

Investigate, and report your findings with sources, before recommending
anything:

1. **What "real-time" actually needs here.** A farmer speaks a question
   (in `en`/`kn`/`te`/`hi`), the system understands it, generates an
   answer grounded in this app's real data (the farmer's actual fields,
   advisories, weather — not a generic LLM answer disconnected from
   AGRO MIRAI's own models), and speaks the answer back, with latency low
   enough to feel like a conversation. Break down which of the following
   AGRO MIRAI already has solved vs. still needs:
   - Speech-to-text in `en`/`kn`/`te`/`hi` — already have
     (`indic-conformer-600m-multilingual` + `whisper-tiny.en`, Module 12).
   - Text-to-speech in `en`/`kn`/`te`/`hi` — already have (Piper +
     vits_rasa_13, Module 25), except the Hindi Piper voice file still
     needs downloading per the current `CLAUDE.md` known limitation.
   - What's actually missing: (a) a way to turn a free-form spoken
     question into a real answer grounded in this farmer's real data
     (an LLM call with retrieval over `DecisionEngine`/`DataStore`
     output, not a canned script), and (b) low enough round-trip latency
     that STT → LLM → TTS feels conversational rather than a slow
     request/response cycle.
2. **Candidate approaches — investigate all three, don't default to the
   first one found:**
   - **(a) Compose it from what's already here**: keep AI4Bharat STT/TTS
     exactly as-is, add one new LLM call in between (a free-tier LLM API
     — check current free-tier limits and terms for Anthropic, Google
     Gemini, or another provider that's genuinely free at low volume) fed
     a real prompt built from the farmer's actual field/advisory data,
     synthesize the reply back through the existing TTS. This keeps every
     already-verified Indian-language voice capability and only adds one
     new integration surface.
   - **(b) A "realtime" voice API end-to-end** (OpenAI Realtime, Gemini
     Live, or similar): check each candidate's actual, current model card
     or docs page for explicit Kannada and Telugu speech support (not
     just "multilingual" marketing copy — name the exact supported
     language list) and its actual free-tier terms (rate limits, whether
     it's free indefinitely or a time-boxed trial, any card-on-file
     requirement). If none genuinely covers `kn`/`te` speech-to-speech,
     say so plainly — that's a real, useful negative finding, not a
     failure to report.
   - **(c) A middle path**: a realtime API for `en`/`hi` (where coverage
     is more likely genuine) composed with the existing AI4Bharat path
     for `kn`/`te`, mirroring the exact TTS-backend-split pattern Module
     25 already established (`kn`/`te` → vits_rasa_13, `en`/`hi` → Piper)
     — reuse that precedent rather than inventing a new one.
3. **"Independent of all the users and their data" — Ritesh's own
   phrasing.** Confirm what this means concretely: each farmer's
   conversation/voice session must be scoped to their own farmer id
   (existing `/v2` auth already provides this — reuse it, don't build new
   auth) and one farmer's voice questions/answers must never leak into or
   influence another farmer's session or data. Confirm whichever
   candidate approach is chosen supports per-farmer request scoping
   cleanly, and flag if any candidate's free tier pools usage/context
   across a shared account in a way that risks cross-farmer bleed.
4. **Cost and quota reality check.** For each candidate, report actual
   current free-tier limits (requests/day, tokens/month, audio
   minutes/month — whatever the provider's real unit is) and what happens
   at the limit (hard stop vs. paid overage) — this is a capstone project
   with no committed budget, so a candidate that silently starts billing
   at scale is a real risk to flag, not a detail to skip.

## What to report back (no code yet)

```
Module: 30 — Voice AI research (stop-and-report)
Status: report-delivered, awaiting decision

Part 1 — Live verification:
  Disease-scan fix: <real log pasted, working / still broken with exact error>
  Language switch: <real before/after screenshots, working / still broken>

Part 2 — Voice AI findings:
  What AGRO MIRAI already has: <STT/TTS coverage recap, with the Hindi-Piper gap noted>
  What's actually missing: <the LLM-grounding + latency gap, stated plainly>
  Candidate (a) compose-with-existing: <findings, free-tier terms, sources>
  Candidate (b) realtime API end-to-end: <per-provider kn/te coverage findings — explicit yes/no per provider, with the source that says so — and free-tier terms>
  Candidate (c) middle path: <findings>
  Per-farmer isolation: <confirmed how, for the leading candidate>
  Cost/quota reality: <real numbers per candidate>
  Recommendation: <one candidate, with reasoning — but this is a recommendation, not a decision; wait for Ritesh's go-ahead before implementing>

Next step: awaiting Ritesh's decision on which candidate to build
```

Do not proceed to implementation after filing this report. Wait for an
explicit go-ahead on which candidate to build, the same way Module 26
waited for the direct-SDK-vs-Flask-proxy decision before writing code.
