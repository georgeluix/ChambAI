# Chamba Segura — local detection of fake job ads linked to human trafficking

**Subtitle:** Gemma 4 E2B, running 100% on-device, analyzes Peruvian job ads and explains — with the government's own open data — why an offer is dangerous, without the ad ever leaving your machine.

**Track:** AI for Social Impact · SDG 5 (Gender Equality) and SDG 1 (No Poverty)
**Team SOINAR:** Abel Mancilla, Jorge Cruzado, Frank Chuctaya

---

## The problem, computed from the primary source

In Peru, the entry point to human trafficking is not abduction — it is a job ad. We processed the Peruvian National Police's public dataset of trafficking complaints (Peru Open Data Portal, 180,600 records, 2017–2023), and the result is unambiguous: **of 3,822 complaints with a recorded recruitment channel, 72.9% began with a fake job offer**. We are not quoting that figure from a report — it is computed by `datos/procesar_dataset.py` in our repo, reproducible line by line. The Public Prosecutor's Office corroborates it independently: 73.8% for the first half of 2023.

The same dataset shows who this crime targets: 86.2% of victims are women, 85.7% of them are between 12 and 29 years old, and 75.6% completed secondary school at most. The dominant method is deception (60.2%), and in regions such as Madre de Dios — illegal mining country — 91.3% of complaints started with a job offer.

Today, someone who suspects an ad has nowhere to check it. Chamba Segura gives them an answer in seconds: explained, and backed by the local statistic behind the alert.

## What it does

The user pastes the text of an ad — or uploads the Facebook/WhatsApp screenshot, which is how these ads actually circulate — and gets back:

- **RISK: low / medium / high**
- **FLAGS:** the concrete signals detected, drawn from a catalog of 21 indicators built on the recruitment patterns documented by Peru's Interior Ministry (screening by physical appearance, relocation with a prepaid ticket, ID document retention, fees charged to the applicant, demands for secrecy from family…)
- **EXPLANATION** in plain language and, at high risk, a prompt to report to **Línea 1818**, the Interior Ministry's trafficking hotline
- **Local context:** if the ad mentions a place ("travel to Puerto Maldonado"), the system responds with that region's real statistics

## How we use Gemma 4 (and why it is the core)

Gemma 4 E2B runs **locally on Ollama** (num_ctx=16384) on a laptop with an 8 GB RTX 3070 Ti. It is the heart of the system in two roles:

1. **Multimodal extraction:** Gemma 4's native vision transcribes the ad text from the screenshot verbatim, preserving misspellings and emojis. The user can correct the transcription before analysis — auditable by design.
2. **Analysis:** the text transformer classifies risk and argues the flags few-shot against our catalog.

Around the model, a **LangGraph** graph orchestrates five nodes (extract → rules → analyze → contextualize → consolidate) behind **FastAPI**, with a **React** frontend. Two architectural decisions matter:

- **Deterministic rules override the model.** Recruiting minors and charging the applicant force high risk in code, not by learned pattern: Article 153 of Peru's Criminal Code makes the recruitment of a minor a completed offense on its own, and a legal line like that cannot depend on probabilities. Every flag carries its origin (`model` or `rule`), visible in the interface.
- **Privacy-first, for real.** Everything runs without internet; the backend never persists an analyzed ad. Consistent with Law 29733, the same statute that protects the victims whose data this crime exploits.

## Open data as calibration, not decoration

The police dataset contains no ad text — it is counts. We use it where it genuinely helps:

- **At inference time:** a compact module (`datos_trata.py`, a 49 KB JSON, zero dependencies) detects regions mentioned in the ad and returns their real figures. The model never memorizes statistics: they are quoted from the source, exactly.
- **In the training data:** we generated a synthetic corpus whose signal distribution **is derived from the real frequencies of the 3,822 complaints** — deception at 60.2%, nightclubs and brothels as the leading exploitation venues, destinations weighted by complaints involving labor-based recruitment. We mixed it with 25 real ads collected from Peruvian classifieds and job portals, anonymized (a PII checker is included in the repo) and traceable by URL. Every line of the corpus carries its `origen` field.

We deliberately chose **not** to mass-collect real recruitment ads: publishing phone numbers and names in a public repo would violate competition rule 1.7 and Law 29733, and compiling a directory of active recruitment channels is harmful in itself. A synthetic corpus calibrated against official data is the ethically defensible alternative — and a reproducible one.

## The hard part: six silent failures and a gated pipeline

We attempted to fine-tune Gemma 4 E2B with LoRA within the laptop's 8 GB. We built a pipeline with validation gates (data → template → canary → adapter) because there was only time for a single training run. It ended up intercepting **six failures, none of which raised an error**:

1. `prepare_model_for_kbit_training` casts the multimodal towers to fp32 → instant OOM.
2. `target_modules="all-linear"` collides with the vision tower's `Gemma4ClippableLinear`, which peft does not support.
3. Without `use_reentrant=False`, grad_norm=0: training "runs" while learning nothing.
4. bitsandbytes does not quantize embeddings: Gemma 4's per-layer table (262,144 × 8,960) is **4.7 GB of invisible bf16** that left only 0.5 GB free. We moved it to RAM behind a CPU lookup (model: 6.94 → 2.16 GB).
5. TRL's `completion_only_loss` reported the mask as applied, but it covered 99% of the tokens — the loss was training on the ad, not on the answer. We caught it by inspecting the actual `completion_mask` and rebuilt the mask by hand.
6. The trained adapter (loss 0.335) scores 3.43 when reloaded from disk — the learning does not survive serialization. Intermediate checkpoints behave identically: the failure is in the stack's train/inference mismatch, not in the saving step.

With failure 6 unresolved two hours before the deadline, we applied the rule we had agreed on in advance: **few-shot, no debate**. Gate 4 ("did it finish?" ≠ "did it work?") stopped us four times from shipping an adapter that emitted generic markdown while its training metrics glowed green. That gated pipeline, with timestamps and logs, is complete in the repo.

## Honest evaluation

20 hand-written cases using real social-media phrasing (emojis, all-caps, misspellings), disjoint from every corpus — Gate 1 verifies the absence of leakage. Results for the demo stack (Gemma 4 E2B + few-shot via Ollama, **excluding** the deterministic rules, which can only improve the outcome):

| Metric | Result |
|---|---|
| RISK accuracy | **85%** (17/20) |
| Missed high-risk ads (the error that matters) | **0 of 8** — no dangerous ad underrated |
| high↔low confusions | 0 |
| Parseable format | 100% (20/20) |
| Speed | **117 tok/s** on an 8 GB laptop GPU (~6 s per analysis) |

All 3 errors are the same type: ambiguous cases classified `medium → high`. For a protection tool, erring toward caution is the right direction of error — the unacceptable failure is the inverse, and it happened zero times. The script (`evaluar_ollama.py`) and the raw results are in the repo.

## Why these were the right calls

A local E2B is not a limitation — it is the requirement. The target population — young women, in the provinces, on intermittent connectivity — cannot depend on a paid API, and a suspicious ad is exactly the kind of data that should not be uploaded to the cloud. Gemma 4 E2B is today the only open model that combines native vision, fluent Spanish, and an 8 GB VRAM footprint. The honesty of the fine-tuning attempt — documented, measured, and discarded on evidence — is worth more than a dressed-up adapter: the system we are presenting is the one that actually works.

## Next steps

Fix the adapter serialization (issue documented), package it as a desktop app requiring no technical setup, and take the flag catalog to validation with CHS Alternativo and the National Police's Anti-Trafficking Directorate.

---

*Public repository and demo attached. Sources: Peru Open Data Portal (dataset 6522273, PNP/MININTER 2017-2023); Report on the National Policy against Human Trafficking, H1 2023.*
