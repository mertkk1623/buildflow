# BuildFlow AI — V1 Product & Development Roadmap

**Document status:** Product direction and implementation roadmap  
**Version:** 1.0  
**Date:** 13 November 2026  
**Working name:** BuildFlow AI  
**Product category:** AI-assisted construction procurement / BOQ intelligence  
**Primary goal:** Build a polished, portfolio-ready SaaS-style application that solves one real construction workflow exceptionally well.

---

## 1. Product decision

We will build **BuildFlow AI**, an AI-assisted tool that turns a construction Bill of Quantities (BOQ) Excel file into a reviewed, traceable, purchase-ready material list.

The user uploads a BOQ. The application interprets material descriptions, matches them against a material catalog, asks the user to resolve uncertain matches, calculates material requirements, consolidates repeated materials and generates Excel/PDF outputs.

### Product promise

> Turn a construction BOQ into a clear, reviewed material purchase list — with AI-assisted material recognition and transparent calculations.

This is not intended to be a complete construction ERP, estimating suite, structural design package or quantity-takeoff system.

### The problem we solve

Construction BOQs often contain inconsistent or abbreviated material descriptions. Preparing a purchase list requires someone to:

- understand and normalize the material descriptions;
- identify which catalog item each line refers to;
- resolve ambiguous material variants;
- convert units where necessary;
- account for waste assumptions;
- consolidate repeated materials;
- calculate purchase quantities using commercial lengths;
- prepare a clear list that purchasing staff can use.

BuildFlow AI brings this workflow into one guided process.

---

## 2. Product principles

These principles govern every design and implementation decision.

1. **One workflow, done well.** Do not turn V1 into a collection of unrelated construction tools.
2. **AI must do visible, useful work.** AI interprets material descriptions and proposes catalog matches. It is not a decorative chatbot.
3. **Calculations must be deterministic.** Python calculation logic owns quantities, unit conversions, waste, consolidation and commercial-length rounding. AI must never invent or alter calculated values.
4. **Uncertainty must be visible.** Uncertain matches require user review. The application must not silently guess.
5. **SaaS-quality experience first.** Design the complete user journey and visual system before building the calculation backend.
6. **Portfolio quality matters.** The finished product must have a coherent interface, a compelling demo scenario, documentation, screenshots and a public live demo.
7. **Finish V1 before expanding.** No feature creep, no premature multi-user SaaS infrastructure.

---

## 3. Target user and V1 scenario

### Primary user

A construction professional, quantity surveyor, site/project engineer or purchasing team member who receives a BOQ in Excel and needs to prepare a material purchase list.

### V1 demonstration scenario

Use a deliberately prepared **light-gauge steel construction BOQ** as the main demo scenario. This gives the product a coherent and realistic story and uses the project's construction-engineering context naturally.

The demo should show a small but varied BOQ containing structural steel items, repeated materials, different units, incomplete descriptions and ambiguous variants.

The application is a BOQ-to-material-planning tool, not a light-steel house design or turnkey house cost estimator. It does not derive quantities from a 70 m² house description or replace architectural/structural design.

---

## 4. V1 user journey

The product should guide the user through one clear sequence.

1. **Dashboard / Start**
   - Explain what the product does.
   - Offer “Start with demo” and “Upload BOQ”.
   - Show a simple recent-activity or demo-project area only if it can be implemented without a database.

2. **Upload BOQ**
   - Upload the supported Excel template.
   - Explain the required columns and supported units.
   - Allow the user to download the blank template.
   - Validate the file and show clear, actionable errors.

3. **AI material review**
   - Parse BOQ rows and identify material descriptions.
   - Match clear items to the material catalog using deterministic rules first.
   - Use AI to interpret unresolved descriptions and suggest catalog candidates.
   - Show the original BOQ description, suggested material, confidence label and short rationale.
   - Let the user accept or change a suggestion.
   - Never send quantities to the AI matching step.
   - Never allow an unapproved AI suggestion into calculations.

4. **Calculation**
   - Calculate only approved/resolved rows.
   - Apply the waste rate from the BOQ row or catalog default, visibly identifying its source.
   - Convert supported units.
   - Consolidate rows by material code.
   - Calculate purchase quantities using the material's commercial length.
   - Keep a trace from every purchase-list line back to its source BOQ rows.

5. **Results**
   - Present a clear summary: rows reviewed, automatically matched, user-approved, unresolved and materials to purchase.
   - Show the consolidated purchase list.
   - Clearly mark the result as **FULL LIST** or **PARTIAL LIST**.
   - Explain excluded rows and why they were excluded.
   - Provide a short AI-generated interpretation based only on actual calculation results.

6. **Export**
   - Download a formatted Excel workbook.
   - Download a concise PDF purchase report.
   - Make the FULL/PARTIAL status and limitations visible in both outputs.

---

## 5. V1 feature scope

### Must have

| Area | V1 capability |
|---|---|
| Input | Excel BOQ upload using one documented template |
| Demo | Built-in sample BOQ and sample catalog |
| Catalog | Small verified starter catalog |
| Matching | Deterministic matching for clear cases |
| AI | AI-assisted interpretation and suggestions for unresolved material descriptions |
| Review | User approval/change for uncertain matches |
| Calculation | Unit conversion, net/gross quantity, waste, consolidation and commercial-length rounding |
| Traceability | Source BOQ rows and calculation details |
| Results | Summary, purchase list, excluded rows and FULL/PARTIAL status |
| AI insight | Short summary grounded in actual application results |
| Export | Excel and PDF |
| Language | Turkish user interface and Turkish reports |
| Resilience | Core workflow remains usable if AI is unavailable; unresolved rows remain for manual review |

### Explicitly out of scope

- 70 m² / 2+1 house configuration or turnkey house cost estimation
- Architectural or structural design
- CAD/PDF drawing quantity takeoff
- Cutting optimization and nesting
- Cost estimation, live supplier prices, labor pricing or quotations
- ERP, accounting, supplier or marketplace integrations
- User accounts, subscriptions, billing and team workspaces
- Persistent project database or multi-project management
- Full catalog-management interface
- Mobile-native application
- General-purpose construction chatbot
- Additional construction calculators unrelated to the BOQ workflow

Do not add any of these to V1 without an explicit product decision.

---

## 6. AI design: meaningful, bounded and demonstrable

AI is a central product feature, but it has a narrow responsibility.

### AI capability 1 — Material description interpretation

AI receives:
- the BOQ material description;
- relevant candidate catalog entries;
- the allowed material identity attributes.

AI returns:
- selected candidate material code, if one is supported;
- confidence label;
- concise reason;
- ambiguity or missing-attribute note when relevant.

AI does **not** receive quantities for the matching task and does not calculate quantities, waste, tonnage or purchase lengths.

### AI capability 2 — Result interpretation

After deterministic calculations finish, AI may summarize:
- how many rows were processed;
- how many were matched automatically;
- how many required approval;
- how many remain unresolved;
- the main issues that prevent a full list;
- notable purchase-list observations that are directly supported by calculated data.

The application supplies the actual figures. AI may explain them but may not create, alter or estimate them.

### AI safety and fallback

- Validate AI output against a strict schema.
- Reject material codes that do not exist in the active catalog.
- Reject suggestions that contradict explicitly stated group, dimensions, grade or coating.
- Require user approval for AI suggestions.
- Show AI unavailability gracefully.
- Never make AI availability a prerequisite for deterministic calculations.
- Do not describe confidence labels as statistically calibrated unless they have actually been evaluated against a sufficiently large labeled dataset.

### What makes the AI demo convincing

The demo must include examples where:
- AI correctly interprets an abbreviated or inconsistent description;
- AI identifies ambiguity and offers more than one candidate;
- the user approves or changes the suggestion;
- the final calculation uses the approved catalog material;
- the result summary reflects the real processed data.

A chatbot window alone does not count as meaningful AI functionality.

---

## 7. Calculation and material-data boundaries

The calculation engine should remain small, testable and independent from the UI.

### Supported material families for V1

- BOX / rectangular or square hollow sections
- IPE
- HEA
- UPN
- FLAT / flat bar (lama)

Use a deliberately small starter catalog — approximately **12–15 verified entries** for the first end-to-end release. Expand only if the demo scenario genuinely needs it.

### Core calculation responsibilities

- Supported units: m, kg and t.
- Convert t to kg.
- Convert kg to meters using the catalog kg/m value.
- Apply row waste when supplied; otherwise use catalog default waste if present.
- If neither row waste nor catalog default exists, exclude the row from calculations and explain why.
- Consolidate calculated rows by material code.
- Apply commercial-length rounding once after consolidation.
- Preserve source BOQ item numbers.
- Keep internal precision; round only for display.
- Record calculation inputs and outputs for traceability.

### Material identity and matching

A catalog item is identified by:

**Group + Size + Grade + Coating**

- IPE 200 and HEA 200 are different materials.
- S235 and S355 are different materials.
- Black and galvanized are different variants.
- Dimension normalization must be group-specific.
- BOX side dimensions may be treated as orientation-independent where appropriate; wall thickness remains distinct.
- FLAT width and thickness order must be preserved.
- Never use fuzzy numeric matching for dimensions or wall thickness.
- Missing grade/coating or multiple possible variants require user confirmation.
- A supplied material code must exist in the catalog and must not contradict explicitly stated BOQ attributes.

### Catalog quality

Every kg/m value must have a traceable manufacturer or standard-table source. Do not invent values to reach a target catalog size. A smaller verified catalog is better than a larger unreliable one.

---

## 8. Product design direction

The product should look like a modern, credible B2B SaaS application — not a generic Streamlit tool or an engineering spreadsheet.

### Visual direction

- Premium, clean, technical B2B product.
- Clear hierarchy and generous spacing.
- Restrained color palette; use one primary accent color.
- Strong typography and consistent component styling.
- Tables should be readable and information-dense without feeling cluttered.
- AI suggestions should be visually distinct from confirmed matches.
- Errors, warnings and pending approvals should have clear but restrained visual states.
- Use realistic construction/material terminology and credible demo data.
- Avoid decorative charts that do not help the workflow.
- Avoid excessive gradients, glowing effects, fake metrics and generic “AI dashboard” decoration.

### Required screens

1. Landing / product entry or dashboard
2. BOQ upload
3. BOQ analysis / AI material matching
4. Match review and approval
5. Calculation results
6. Purchase list and exports

The design phase must define:
- design tokens;
- typography;
- colors;
- spacing;
- buttons and form controls;
- tables;
- status labels;
- cards;
- navigation;
- responsive behavior for desktop and tablet;
- loading, empty, error and success states.

### Design approval rule

Do not begin the full backend or calculation implementation before:
- the visual direction is agreed;
- all required screens are represented;
- the end-to-end user journey is understandable;
- the main dashboard and matching/results screens are approved.

Small technical spikes are allowed only when necessary to validate feasibility; they must not become premature product development.

---

## 9. Technical direction

The working architecture is:

| Layer | Preferred technology |
|---|---|
| Frontend | React + TypeScript |
| Styling | Tailwind CSS |
| Backend API | Python + FastAPI |
| Calculation engine | Python, Decimal |
| Excel input/output | OpenPyXL |
| PDF output | ReportLab |
| AI | Provider-independent LLM integration behind a small service layer |
| Tests | Pytest; frontend tests where they add meaningful value |
| Version control | Git + GitHub |

### Architecture rules

- Keep frontend and backend responsibilities separate.
- Keep calculation logic independent of FastAPI routes and UI components.
- Keep AI integration isolated behind a small interface so the provider can be changed.
- Validate uploaded files and AI responses at system boundaries.
- Do not introduce a database in V1.
- Do not introduce authentication or subscription infrastructure.
- Use environment variables for API keys; never commit secrets.
- Provide a demo mode that works without an AI key. If AI is unavailable, show a clear fallback state and allow rule-based/manual review.
- Keep dependencies and project structure as simple as possible.

The technology choices may be adjusted only if a concrete implementation constraint justifies it. Do not change the stack merely for novelty.

---

## 10. Development roadmap

The sequence is deliberate: product experience first, then a working demo shell, then deterministic logic, then AI, then release.

### Phase 0 — Project setup and product blueprint

**Goal:** Start cleanly in a new project directory and establish the project foundation.

Deliverables:
- New project folder and Git repository.
- This roadmap saved as `ROADMAP.md`.
- Concise `README.md` describing the product.
- Agreed stack and project structure.
- Basic development instructions.
- No feature implementation yet.

Completion gate:
- Project opens and runs locally with a minimal frontend/backend health check.
- No unnecessary infrastructure has been introduced.

### Phase 1 — SaaS UI/UX prototype

**Goal:** Make the product visible and agree on the experience before building the engine.

Deliverables:
- Design system and reusable UI components.
- All six required screens.
- Responsive desktop/tablet layouts.
- Clickable end-to-end navigation using realistic sample data.
- Upload, matching, approval, results and export states represented.
- Clear loading, empty, error and partial-result states.

The prototype may use mock data. Do not pretend mock calculations or AI responses are real.

Completion gate:
- A user can understand and navigate the entire product journey.
- The user approves the visual direction and core screens.

### Phase 2 — Frontend application shell and demo workflow

**Goal:** Convert the approved prototype into the real frontend structure.

Deliverables:
- Reusable page and component structure.
- Navigation and workflow state.
- Demo BOQ and catalog displayed through the actual UI.
- File-upload interaction and validation states.
- Match review and approval interactions.
- Results and export screens connected to temporary/demo data.

Completion gate:
- The full workflow can be demonstrated in the browser without relying on backend calculations yet.
- Mock/demo data is clearly identified.

### Phase 3 — Backend and deterministic calculation engine

**Goal:** Make the core product genuinely calculate correctly.

Deliverables:
- FastAPI service and validated request/response schemas.
- BOQ Excel parser for the documented template.
- Catalog loader and validation.
- Material normalization and deterministic matching.
- Unit conversion and waste logic.
- Consolidation and commercial-length rounding.
- Source-row traceability.
- Full/partial list status and exclusion reasons.
- Automated tests using independently checked expected results.

Completion gate:
- Known test cases produce expected outputs.
- Invalid and ambiguous rows are not silently included.
- The engine works without an AI API key.

### Phase 4 — AI material recognition and result interpretation

**Goal:** Add the visible AI capability to the real workflow.

Deliverables:
- AI matching for unresolved BOQ descriptions.
- Candidate selection constrained to the active catalog.
- Strict output validation.
- Confidence labels and short rationale.
- User approval before calculation.
- AI result summary grounded in backend results.
- API-unavailable and malformed-response fallback states.
- Tests for invalid codes, contradictory suggestions and AI failure.

Completion gate:
- AI improves the matching workflow in the demo.
- AI cannot change calculation results or bypass approval.

### Phase 5 — Exports, polish and release

**Goal:** Deliver a portfolio-ready application.

Deliverables:
- Formatted Excel workbook with purchase list, calculation trace, excluded rows and findings.
- Concise Turkish PDF report.
- FULL/PARTIAL status in outputs.
- Correct Turkish character rendering.
- Clear notes about theoretical weights, waste assumptions and lack of cutting optimization.
- End-to-end demo scenario.
- UI polish and bug fixes.
- README with screenshots, architecture, features, limitations and setup instructions.
- GitHub repository.
- Public live demo, subject to hosting and API-key constraints.

Completion gate:
- A new user can run the demo, upload the supported BOQ, review matches, obtain a purchase list and export the results.
- The README and live demo accurately describe what works and what does not.

---

## 11. Definition of done

V1 is complete when all of the following are true:

- [ ] The product has a coherent, polished SaaS interface.
- [ ] The full workflow is understandable without explanation.
- [ ] A user can start with the built-in demo.
- [ ] A user can upload the supported BOQ template.
- [ ] Material descriptions are matched deterministically where unambiguous.
- [ ] AI can suggest catalog matches for unresolved descriptions.
- [ ] The user can approve or change suggestions.
- [ ] Unapproved or contradictory suggestions are excluded.
- [ ] Calculations are deterministic and covered by tests.
- [ ] Repeated materials are consolidated correctly.
- [ ] Every purchase line can be traced to BOQ source rows.
- [ ] Partial results are clearly identified.
- [ ] Excel and PDF exports work.
- [ ] The application remains usable when AI is unavailable.
- [ ] GitHub documentation and screenshots are complete.
- [ ] A live demo is available or the deployment limitation is documented.

Once these conditions are met, V1 is finished. Do not keep expanding it for the sake of adding features.

---

## 12. Explicitly deferred ideas

These may be considered only after V1 is released and evaluated:

- Larger material catalogs and additional profiles.
- More BOQ templates and import formats.
- Project history and persistent storage.
- Multi-user collaboration.
- Supplier pricing and cost estimation.
- ERP integrations.
- CAD/BIM takeoff.
- Cutting optimization.
- A separate lightweight-steel house estimating/configurator product.

The 70 m², 2+1 light-steel house from foundation to turnkey cost idea is a possible **separate future product**, not part of BuildFlow AI V1.

---

## 13. Working rules for OpenCode

OpenCode is the implementation environment. It must follow this roadmap rather than redesigning the product scope on its own.

1. Work in small, verifiable phases.
2. Before each phase, state the intended files and acceptance criteria.
3. Do not silently add features or infrastructure.
4. Do not generate large amounts of code before the relevant design or phase is approved.
5. Do not replace real functionality with hardcoded demo claims.
6. Keep demo data clearly separated from user data.
7. Run relevant tests after each backend change.
8. Keep Git commits focused and understandable.
9. Never expose API keys or secrets.
10. When a decision is ambiguous, present the smallest reasonable choice instead of expanding scope.

### First instruction after creating the new project folder

Start with **Phase 0 only**. Inspect the empty/new directory, create the agreed project foundation and documentation, and report the resulting structure and local run instructions. Do not start the SaaS screens, backend features, AI integration or calculation engine until the next phase is explicitly started.
