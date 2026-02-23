# Luemyn MVP Plan

## Executive Summary

Luemyn is a unified AI platform combining **legacy COBOL modernization**, **enterprise document intelligence**, and an **autonomous AI assistant** — delivered through a VS Code extension and a web dashboard.

The MVP brings together three existing systems:
- **Luemyn IDE** (Roo-Code + Luemyn Backend) — COBOL understanding, Q&A, and Java transformation in VS Code
- **ASWA Platform** — Enterprise document ingestion, semantic search, insights, and AI agent workflows
- **Luemyn Autopilot** — An autonomous AI assistant that runs on ASWA, capable of executing complex multi-step tasks end-to-end

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Luemyn VS Code Extension (Roo-Code + Luemyn)          │
│  - COBOL editing, Q&A, one-click convert                │
│  - RAG via Qdrant (built into Roo-Code)                 │
│  - Calls Luemyn backend for parsing/transformation      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Luemyn Backend (Java)                                  │
│  - COBOL parsing, dependency graph (Neo4j)              │
│  - Hybrid COBOL-to-Java transformation                  │
│  - Sync mode (<10 files) / Scheduled mode (>=10 files)  │
│  - Chunking REST API                                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ASWA Platform                                          │
│  - Document intelligence (Google + Microsoft docs)      │
│  - Semantic search, insight extraction                  │
│  - AI Agent platform, notifications                     │
│  - Luemyn Autopilot runs on top of this                 │
└─────────────────────────────────────────────────────────┘
```

---

## Pillar 1: Luemyn IDE (Roo-Code + Luemyn Combined)

The VS Code extension is the primary developer interface. Roo-Code provides the AI coding assistant shell and RAG infrastructure (Qdrant). The Luemyn backend provides COBOL-specific parsing, transformation, and dependency analysis.

| #    | Feature                              | Runs In         | Description |
|------|--------------------------------------|-----------------|-------------|
| 1.1  | COBOL Codebase Indexing & RAG        | Roo-Code        | Load COBOL files, chunk them via Luemyn backend's chunking API, generate embeddings, store in Qdrant (Roo-Code's native vector DB). Enable natural language Q&A over the codebase. |
| 1.2  | Dependency Graph                     | Luemyn Backend  | Parse COBOL programs, build CALL/COPY/PERFORM/SQL dependency graph in Neo4j. Expose via API for the IDE. |
| 1.3  | COBOL Q&A in IDE (Ask Mode)          | Roo-Code        | "What does PROGRAM-X do?", "Which programs call SUBROUTINE-Y?" — powered by Qdrant RAG + Neo4j dependency context. |
| 1.4  | COBOL-Aware Code Mode                | Roo-Code        | AI-assisted COBOL editing — inline explanations, refactoring suggestions, syntax help via Roo-Code's code mode. |
| 1.5  | Architect Mode for Migration         | Roo-Code        | Plan migration strategies — analyze a COBOL program and suggest Java architecture with dependency context. |
| 1.6  | Debug Mode                           | Roo-Code        | Trace COBOL logic, identify root causes, suggest fixes with AI assistance. |
| 1.7  | One-Click Convert                    | Roo-Code + Backend | Right-click COBOL file → "Convert to Java" — calls hybrid transformation pipeline, shows diff in editor. |
| 1.8  | Sync Transformation (<10 files)      | Luemyn Backend  | Real-time conversion — user selects files, gets Java output immediately in the IDE. |
| 1.9  | Scheduled Transformation (>=10 files)| Luemyn Backend  | Offline batch mode — user queues a conversion job, gets notified when complete. Progress tracking in IDE sidebar. |
| 1.10 | Auto Test Generation                 | Luemyn Backend + Roo-Code | LLM-generated test cases for converted Java code. |
| 1.11 | Dependency Explorer Panel            | Roo-Code        | VS Code panel visualizing the Neo4j dependency graph for the loaded COBOL project. |

---

## Pillar 2: ASWA Platform (Enterprise Document Intelligence)

| #   | Feature                  | Description |
|-----|--------------------------|-------------|
| 2.1 | Multi-Source Ingestion   | Connect to Google Docs/Drive and Microsoft OneDrive/SharePoint/Word — ingest and index documents automatically. |
| 2.2 | Email Connectors         | Gmail + Outlook/Exchange ingestion. |
| 2.3 | Messaging Connectors     | Slack + Microsoft Teams ingestion. |
| 2.4 | Semantic Search          | Natural language queries across all enterprise documents with RAG-powered answers and source citations. |
| 2.5 | Insight Extraction       | Auto-extract patterns, entities, relationships, anomalies, and risks from document collections. |
| 2.6 | AI Agent Builder         | Visual workflow builder: triggers (schedule, webhook, email, Slack) → actions (API calls, DB ops, notifications). |
| 2.7 | Approval Workflows       | Human-in-the-loop for sensitive agent actions with escalation. |
| 2.8 | Multi-Channel Notifications | Push insights/alerts via Email, Slack, Teams, webhooks. |

---

## Pillar 3: Luemyn Autopilot (Autonomous AI Assistant, runs on ASWA)

Luemyn Autopilot is an autonomous agent that runs on the ASWA agent platform. It can independently plan, execute, and deliver results for complex multi-step tasks — from research and report generation to data analysis and presentation creation.

| #   | Feature                                  | Description |
|-----|------------------------------------------|-------------|
| 3.1 | Autonomous Multi-Step Task Execution     | Give a high-level goal. Autopilot plans steps, executes them end-to-end without hand-holding, and delivers completed output. Runs on ASWA's agent execution engine with triggers, action blocks, and stateful workflows. |
| 3.2 | Deep Research & Report Generation        | Autopilot browses the web, collects data, synthesizes findings, and produces downloadable reports (Word/PDF/spreadsheet). Cross-references ASWA-ingested enterprise documents for richer context. |
| 3.3 | Data Collection & Structuring            | Gathers information from multiple sources (ASWA documents, web, APIs), structures it into spreadsheets/tables, and delivers organized datasets. |
| 3.4 | Cloud-Based Background Execution         | Tasks run asynchronously on ASWA's infrastructure — user does not need to keep VS Code or the browser open. Autopilot sends notifications (Slack/email/Teams via ASWA's notification service) when work is complete. Progress viewable in the ASWA web dashboard. |

### ASWA Integration Points for Autopilot

| Integration            | How |
|------------------------|-----|
| Execution Engine       | Autopilot tasks are ASWA agents with custom action blocks for general-purpose operations (web browsing, file generation, API calls) and Luemyn-specific operations (parse, transform, analyze COBOL). |
| Document Context       | Autopilot pulls context from ASWA-ingested documents (Google Docs, SharePoint specs, Slack conversations, emails) to inform its work. |
| Notification Delivery  | Uses ASWA's multi-channel notification service to report results via Slack, email, or Teams. |
| Web Dashboard          | Autopilot task status, progress, and downloadable outputs are viewable in ASWA's web dashboard. |
| RAG Cross-Reference    | Autopilot can query both Luemyn's COBOL RAG (Qdrant) and ASWA's document RAG to combine code understanding with business context. |

---

## MVP Demo Script

### Demo 1: "Understand the COBOL Codebase" (IDE)

**Goal**: Show Luemyn's ability to ingest, understand, and answer questions about a COBOL codebase.

1. Open a COBOL project in VS Code with the Luemyn extension.
2. **Index the codebase** — chunks via Luemyn backend, embeddings into Qdrant.
3. **Show Dependency Explorer** panel — interactive graph of programs and relationships.
4. **Ask Mode**: "What does the payroll calculation module do?" — RAG answer with line references.
5. **Ask Mode**: "Which programs would be affected if I change COPYBOOK-X?" — dependency-aware answer.

### Demo 2: "Convert COBOL to Java" (IDE)

**Goal**: Show the hybrid transformation pipeline in both sync and scheduled modes.

1. **Single file (sync)**: Right-click a COBOL file → Convert to Java → see result in seconds with diff view.
2. **Review & refine**: Ask "Is this conversion correct? What edge cases am I missing?"
3. **Auto-generated tests** shown alongside the Java output.
4. **Batch conversion (scheduled)**: Select 25 files → "Schedule Conversion" → job queued → progress bar in sidebar → notification when done.

### Demo 3: "Luemyn Autopilot — Autonomous Work" (on ASWA)

**Goal**: Show Autopilot as a general-purpose autonomous assistant that executes complex multi-step tasks end-to-end.

**Scenario A — Research & Design Doc**:
Type: "Research the top 5 cloud providers' AI offerings, compare pricing and features, and create a design doc with recommendations for our team." Autopilot browses the web, gathers data, and produces a downloadable Word doc with structured comparison tables and a recommendation section.

**Scenario B — Email/Message Triage & Action**:
Type: "Read my unread emails and Slack messages from this week. Summarize the key action items, draft replies for anything urgent, and create a PR for the documentation changes that Sarah requested in her email yesterday." Autopilot scans ASWA-ingested email and Slack, produces a summary, draft replies, and an actual GitHub PR.

**Scenario C — Spreadsheet Analysis & Presentation**:
Type: "Here's our Q4 sales data (Excel). Analyze trends by region, identify the top 3 underperforming segments, and create a presentation with charts summarizing the findings." Autopilot ingests the spreadsheet, runs analysis, and generates a downloadable PowerPoint with charts and talking points.

**Scenario D — Background Execution**:
User kicks off the task and closes the browser. A notification arrives in Slack: "Your sales analysis presentation is ready." Open the ASWA dashboard to download the output.

### Demo 4: "Enterprise Document Intelligence" (ASWA)

**Goal**: Show ASWA as a general-purpose enterprise document platform.

1. Connect to **Google Drive** + **SharePoint** — ingest a mix of strategy docs, meeting notes, and project specs.
2. Search: "What decisions were made about the Q2 product roadmap?" — semantic search returns relevant meeting notes with citations.
3. Show extracted insights: key entities (people, projects, deadlines), relationships between them.
4. Create an agent: "When a new document is uploaded to the Product folder in SharePoint, extract action items and post a summary to #product-updates on Slack."
5. Upload a new doc → show the Slack message arriving automatically.

### Demo 5: "End-to-End Workflow"

**Goal**: Show all three pillars working together under the Luemyn umbrella.

1. **ASWA dashboard**: Autopilot tasks running, document insights, connected sources overview.
2. **VS Code**: open a COBOL program, ask questions, convert it one-click.
3. **Autopilot**: "Read the project kickoff doc from SharePoint, extract the requirements, and create a design document outline" — runs in background, delivers a downloadable doc.
4. **Show everything connected**: the IDE for hands-on coding work, Autopilot for autonomous knowledge work, ASWA for enterprise document intelligence — all under the Luemyn umbrella.

---

## MVP Priority

| Priority | Features | Rationale |
|----------|----------|-----------|
| P0 — Must Have | 1.1, 1.2, 1.3, 1.7, 1.8, 1.9 | Core value prop: COBOL indexing/RAG, dependency graph, Q&A, sync + scheduled transformation. |
| P0 — Must Have | 1.4, 1.11 | Essential IDE experience: COBOL Code Mode, Dependency Explorer. |
| P1 — High Value | 3.1, 3.2, 3.4 | Differentiator: Autopilot autonomous execution, report generation, background execution on ASWA. |
| P1 — High Value | 2.1, 2.4 | Required for Autopilot context: Google + Microsoft doc ingestion, semantic search. |
| P2 — Important | 1.5, 1.10 | Migration quality: Architect Mode, auto test generation. |
| P2 — Important | 3.3 | Useful but not essential for first demo: data collection & structuring. |
| P3 — Later | 2.5, 2.6, 2.7, 2.8 | ASWA platform depth: insight extraction, agent builder, approval workflows, notifications. |
| P3 — Later | 1.6 | Nice-to-have for MVP: Debug Mode. |

---

## Core MVP Story

> Point Luemyn at a COBOL codebase in VS Code — it understands, explains, and converts it. For large migrations, schedule batch conversions and track progress. Beyond code, Luemyn Autopilot autonomously executes complex knowledge work — research, reports, data analysis, presentations — running in the cloud on the ASWA platform, pulling context from your enterprise documents across Google and Microsoft ecosystems.
