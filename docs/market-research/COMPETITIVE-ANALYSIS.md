# ASWA Competitive Analysis & Market Strategy

## Executive Summary

The enterprise AI market is converging around three capabilities: **document intelligence**, **AI agents**, and **workflow automation**. Today, these are served by separate platforms - Glean for search, Moveworks for IT automation, Relevance AI for agents. ASWA's opportunity is to be the **first unified platform** that combines all three with **enterprise-grade deployment flexibility** and **no-code agent creation**.

**Strategic Position**: Enterprise Document Intelligence Platform with User-Created AI Agents

---

## Market Landscape

### The Three Pillars of Enterprise AI

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE AI MARKET MAP                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│         DOCUMENT INTELLIGENCE          AI AGENTS          WORKFLOW      │
│         (Search & Understanding)       (Autonomous)       (Automation)  │
│                                                                         │
│         ┌─────────────┐          ┌─────────────┐    ┌─────────────┐    │
│         │   Glean     │          │ Relevance AI│    │   Workato   │    │
│         │   Dust.tt   │          │  Lindy.ai   │    │   Tray.ai   │    │
│         │   Guru      │          │  CrewAI     │    │   n8n       │    │
│         │ Notion AI   │          │  AutoGPT    │    │   Zapier    │    │
│         └─────────────┘          └─────────────┘    └─────────────┘    │
│                                                                         │
│         ┌─────────────────────────────────────────────────────────┐    │
│         │                    CONVERSATIONAL AI                     │    │
│         │     Cognigy  •  Voiceflow  •  Botpress  •  Kore.ai      │    │
│         │                  (Customer Service Focus)               │    │
│         └─────────────────────────────────────────────────────────┘    │
│                                                                         │
│         ┌─────────────────────────────────────────────────────────┐    │
│         │                      HYPERSCALERS                        │    │
│         │   Microsoft Copilot  •  Vertex AI  •  Bedrock Agents    │    │
│         │             (Platform Lock-in, Cloud Only)              │    │
│         └─────────────────────────────────────────────────────────┘    │
│                                                                         │
│                           ★ ASWA OPPORTUNITY ★                          │
│              Unified: Documents + Agents + Automation                   │
│              Flexible: SaaS → On-Prem → Air-Gap                         │
│              Accessible: No-Code Agent Builder                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Competitor Deep Dive

### Category 1: Enterprise Search & Document Intelligence

| Platform | Description | Funding/Valuation | Key Strength | Key Weakness |
|----------|-------------|-------------------|--------------|--------------|
| **Glean** | Enterprise AI search | $200M+ / $4.6B | Best search relevance | SaaS-only, read-only, no agents |
| **Dust.tt** | AI assistants on company knowledge | $16M | Great UX, knowledge sync | Early stage, no on-prem |
| **Guru** | Knowledge management | $80M+ | Knowledge verification | Limited AI capabilities |
| **Notion AI** | AI in Notion workspace | Part of Notion | Native integration | Notion-only ecosystem |

#### Glean - Primary Competitor

```
Company: Glean (founded 2019 by ex-Google)
Valuation: $4.6 billion (2024)
Focus: Enterprise search across 100+ apps

PRODUCT:
├─ Unified search across all enterprise apps
├─ Glean Assistant (AI Q&A with citations)
├─ Glean Apps (custom AI assistants)
└─ Knowledge graph of people/content/activities

STRENGTHS:
├─ Best-in-class search relevance
├─ Strong organizational context understanding
├─ 100+ pre-built connectors
├─ Excellent UX
└─ Strong enterprise security (SOC2, GDPR)

WEAKNESSES:
├─ SaaS-only (data leaves customer premises)
├─ Read-only (cannot take actions)
├─ No autonomous agents
├─ No workflow automation
├─ High price ($10-15/user/mo)
└─ No on-prem for regulated industries

DEPLOYMENT: Cloud only (AWS)
ON-PREM: Not available
AIR-GAP: Not supported
```

#### Dust.tt - Emerging Competitor

```
Company: Dust.tt (founded by ex-OpenAI)
Funding: $16M (Seed/Series A)
Focus: Custom AI assistants on company data

PRODUCT:
├─ AI assistants connected to company tools
├─ Real-time data sync (Notion, Slack, Drive)
├─ "Company brain" knowledge retrieval
└─ Custom assistant builder

STRENGTHS:
├─ Excellent developer experience
├─ Strong knowledge retrieval
├─ Real-time data connections
├─ Good Notion/Slack integration
└─ Growing tech company adoption

WEAKNESSES:
├─ SaaS-only
├─ Limited workflow automation
├─ No visual agent builder
├─ Early enterprise features
└─ Smaller connector ecosystem

DEPLOYMENT: Cloud only
ON-PREM: Not available (exploring)
```

---

### Category 2: AI Agent Platforms

| Platform | Description | Funding/Valuation | Key Strength | Key Weakness |
|----------|-------------|-------------------|--------------|--------------|
| **Relevance AI** | AI workforce platform | $18M | No-code agent builder | SaaS-only, no documents |
| **Lindy.ai** | Personal AI assistants | $50M+ | Consumer-friendly | Not enterprise-ready |
| **CrewAI** | Multi-agent orchestration | $18M | Multi-agent workflows | Code-only |
| **AutoGPT** | Autonomous goal-driven agents | $12M | Viral awareness | Not production-ready |
| **Adept AI** | AI that uses software like humans | $415M / $1B+ | Foundational research | Limited availability |

#### Relevance AI - Key Agent Competitor

```
Company: Relevance AI (Australia)
Funding: $18M Series A
Focus: No-code AI workforce platform

PRODUCT:
├─ AI "workers" for various tasks
├─ No-code visual builder
├─ Multi-step agent workflows
├─ Pre-built agent templates
└─ Tool/integration ecosystem

STRENGTHS:
├─ Best no-code agent experience
├─ Good documentation
├─ Multi-agent orchestration
├─ Growing template library
└─ Developer-friendly API

WEAKNESSES:
├─ SaaS-only
├─ Limited document intelligence
├─ No enterprise compliance features
├─ Smaller brand recognition
└─ Weak knowledge base integration

DEPLOYMENT: Cloud only
ON-PREM: Not available
AGENT CREATION: No-code visual + NLP
```

#### Lindy.ai - Consumer/Prosumer Agent

```
Company: Lindy.ai
Funding: $50M+ (Series A 2024)
Focus: Personal AI assistants

PRODUCT:
├─ Personal task automation
├─ Email/calendar integration
├─ "Societies of agents" multi-agent
└─ Natural language creation

STRENGTHS:
├─ Very user-friendly
├─ Quick personal agent deployment
├─ Good calendar/email automation
└─ NLP-based agent creation

WEAKNESSES:
├─ Not enterprise-focused
├─ Limited security/compliance
├─ Shallow integrations
└─ No document intelligence

DEPLOYMENT: SaaS only
AGENT CREATION: Natural language primarily
```

---

### Category 3: Enterprise Automation Platforms

| Platform | Description | Funding/Valuation | Key Strength | Key Weakness |
|----------|-------------|-------------------|--------------|--------------|
| **Workato** | Enterprise automation | $290M / $5.7B | 1000+ connectors, enterprise-proven | Expensive, not agent-focused |
| **Tray.ai** | General automation platform | $150M+ | Deep enterprise integrations | Complex, expensive |
| **n8n** | Open-source workflow automation | $12M | Self-hosted, flexible | Technical users only |
| **Zapier** | Consumer/SMB automation | $160M / $5B | Easy to use, huge adoption | Not enterprise-grade |

#### Workato - Enterprise Automation Leader

```
Company: Workato (acquired by Vista Equity)
Valuation: $5.7 billion
Focus: Enterprise automation platform

PRODUCT:
├─ Visual "recipe" builder
├─ 1000+ enterprise connectors
├─ AI Copilot for building workflows
├─ Workbot for Slack/Teams
└─ Enterprise governance

STRENGTHS:
├─ Largest connector ecosystem
├─ Enterprise-proven at scale
├─ Strong IT governance
├─ AI-assisted building
└─ Reliable and mature

WEAKNESSES:
├─ Expensive ($25K-500K+/year)
├─ Not agent-focused (task-based)
├─ Complex pricing
├─ Steep learning curve
└─ No document intelligence

DEPLOYMENT: SaaS + hybrid gateway
ON-PREM: Partial (on-prem gateway)
```

---

### Category 4: Conversational AI / IT Automation

| Platform | Description | Funding/Valuation | Key Strength | Key Weakness |
|----------|-------------|-------------------|--------------|--------------|
| **Moveworks** | IT/HR automation | $200M / $2.1B | IT service desk automation | SaaS-only, narrow focus |
| **Cognigy** | Enterprise conversational AI | $100M+ / $1.5B | Full deployment flexibility | Contact center focus |
| **Voiceflow** | Conversational design platform | $20M+ | Best visual designer | Less agent-focused |
| **Botpress** | Open-source conversational AI | $22M | Self-hosted, GPT-native | Technical users |
| **Kore.ai** | Enterprise virtual assistants | $150M+ | Full on-prem support | Requires development |

#### Moveworks - IT Automation Competitor

```
Company: Moveworks
Funding: $200M+ / $2.1B valuation
Focus: IT/HR service desk automation

PRODUCT:
├─ Conversational IT support
├─ Automated ticket resolution
├─ Password resets, software provisioning
├─ Knowledge article suggestions
└─ ITSM integrations (ServiceNow, Jira)

STRENGTHS:
├─ Best IT automation metrics
├─ Proven ticket deflection
├─ Deep ServiceNow integration
├─ Multi-language support
└─ Strong enterprise adoption

WEAKNESSES:
├─ SaaS-only
├─ Narrow IT/HR focus
├─ Limited document intelligence
├─ No custom agent creation
├─ High implementation cost
└─ Not suitable for general workflows

DEPLOYMENT: Cloud only (GCP)
ON-PREM: Not available
```

#### Cognigy - Deployment Flexibility Leader

```
Company: Cognigy (Germany)
Funding: $100M+ / $1.5B valuation
Focus: Enterprise conversational AI

PRODUCT:
├─ Visual flow builder (Cognigy.AI)
├─ 100+ language support
├─ Omnichannel deployment
├─ Enterprise NLU
└─ Contact center focus

STRENGTHS:
├─ Full deployment flexibility
├─ Best multilingual support
├─ Strong compliance (SOC2, HIPAA, GDPR)
├─ Proven enterprise scale
└─ On-premise available

WEAKNESSES:
├─ Contact center focused
├─ Not document-intelligence focused
├─ Complex implementation
├─ Higher cost
└─ Conversational, not autonomous agents

DEPLOYMENT: SaaS, Private Cloud, On-Premise
ON-PREM: Fully supported
AIR-GAP: Supported
```

---

### Category 5: Hyperscaler Platforms

| Platform | Description | Deployment | Key Strength | Key Weakness |
|----------|-------------|------------|--------------|--------------|
| **Microsoft Copilot Studio** | M365 agent builder | Azure Cloud | Deep M365 integration | Microsoft lock-in |
| **Google Vertex AI Agent** | GCP agent platform | Google Cloud | Gemini + Search grounding | GCP lock-in |
| **Amazon Bedrock Agents** | AWS agent service | AWS | Multi-model choice | Complex, AWS expertise needed |
| **OpenAI GPTs/Assistants** | Custom GPTs | OpenAI Cloud | Best models, easy start | No on-prem, limited depth |

#### OpenAI GPT Builder / Assistants API

```
Company: OpenAI
Focus: Custom GPTs and Assistants API

PRODUCT:
├─ GPT Builder (consumer, NLP-based)
├─ Assistants API (developer, code + config)
├─ Code Interpreter
├─ Retrieval / File Search
├─ Function calling
└─ GPT Store distribution

STRENGTHS:
├─ Easiest path to AI agents
├─ Best foundation models
├─ Massive user base
├─ Rapid innovation
└─ Great developer experience

WEAKNESSES:
├─ OpenAI hosted only
├─ Data privacy concerns for enterprise
├─ Vendor lock-in
├─ Limited workflow complexity
├─ GPTs lack depth for enterprise
└─ No on-premise option

DEPLOYMENT: OpenAI cloud only
ON-PREM: Not available
AGENT CREATION: NLP (GPTs) + Code (Assistants)
```

#### Microsoft Copilot Studio

```
Company: Microsoft
Focus: Enterprise copilot/agent builder

PRODUCT:
├─ Visual designer for agents
├─ Natural language topic creation
├─ Power Automate integration
├─ SharePoint/Teams native
├─ Dataverse connectivity
└─ M365 security compliance

STRENGTHS:
├─ Deep Microsoft 365 integration
├─ Enterprise security (FedRAMP High)
├─ Existing customer relationships
├─ Unified platform play
└─ Azure Government option

WEAKNESSES:
├─ Microsoft ecosystem lock-in
├─ Complex pricing
├─ Weaker outside MS ecosystem
├─ Less flexible than pure-plays
└─ No true on-prem (cloud-dependent)

DEPLOYMENT: Azure Cloud (Azure Gov for government)
ON-PREM: Not available
AGENT CREATION: Visual + NLP + Code extensions
```

---

## Deployment Strategy Comparison

### The Enterprise Deployment Gap

Most AI platforms are **SaaS-only**, blocking adoption in regulated industries:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT OPTIONS BY VENDOR                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Vendor              SaaS   Private   On-Prem   Air-Gap   BYOLLM        │
│  ────────────────────────────────────────────────────────────────────── │
│  Glean               ✓      Limited    ✗         ✗         ✗           │
│  Dust.tt             ✓      ✗          ✗         ✗         ✗           │
│  Moveworks           ✓      Limited    ✗         ✗         ✗           │
│  Relevance AI        ✓      ✗          ✗         ✗         ✗           │
│  Lindy.ai            ✓      ✗          ✗         ✗         ✗           │
│  OpenAI GPTs         ✓      ✗          ✗         ✗         ✗           │
│  Workato             ✓      Partial    ✗         ✗         ✗           │
│  ─────────────────────────────────────────────────────────────────────  │
│  Cognigy             ✓      ✓          ✓         ✓         Partial     │
│  Botpress            ✓      ✓          ✓         ✓         ✓           │
│  Kore.ai             ✓      ✓          ✓         ✓         ✓           │
│  n8n                 ✓      ✓          ✓         ✓         ✓           │
│  ─────────────────────────────────────────────────────────────────────  │
│  Microsoft Copilot   ✓      Azure Gov  ✗         Partial   ✗           │
│  Vertex AI Agent     ✓      ✓          ✗         ✗         ✗           │
│  Bedrock Agents      ✓      ✓          ✗         Partial   ✓           │
│  ─────────────────────────────────────────────────────────────────────  │
│  ASWA (Target)       ✓      ✓          ✓         ✓         ✓           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Blocked Markets (SaaS-Only Limitation)

| Segment | Requirement | TAM | Served Today |
|---------|-------------|-----|--------------|
| US Government | FedRAMP, air-gap capable | $50B+ | Microsoft (partial) |
| Defense/IC | IL5/6, air-gap mandatory | $15B+ | None |
| Healthcare | HIPAA, on-prem preferred | $30B+ | Cognigy, Kore.ai |
| Financial Services | On-prem, audit requirements | $40B+ | Cognigy, Kore.ai |
| EU Enterprise | GDPR data residency | $25B+ | Microsoft, some |

**ASWA Opportunity**: Serve these blocked markets with full deployment flexibility.

---

## Agent Creation Methods Comparison

### How Users Create Agents Today

| Platform | NLP Prompt | Form Builder | Visual Flow | YAML/Config | Code SDK |
|----------|:----------:|:------------:|:-----------:|:-----------:|:--------:|
| **Relevance AI** | ★★★★☆ | ★★★★★ | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ |
| **Lindy.ai** | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ |
| **OpenAI GPTs** | ★★★★★ | ★★☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★☆ |
| **Copilot Studio** | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ |
| **Cognigy** | ★★☆☆☆ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ |
| **Voiceflow** | ★★☆☆☆ | ★★★☆☆ | ★★★★★ | ★★★☆☆ | ★★★☆☆ |
| **CrewAI** | ☆☆☆☆☆ | ☆☆☆☆☆ | ★☆☆☆☆ | ★★★★☆ | ★★★★★ |
| **LangChain** | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ | ★★★★★ |
| **n8n** | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★★☆ | ★★★★★ |
| **ASWA (Target)** | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |

### The Accessibility Gap

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT CREATION USER SPECTRUM                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   BUSINESS USER              POWER USER              DEVELOPER          │
│   (No technical skill)       (Some technical)        (Full technical)   │
│         │                         │                        │            │
│         ▼                         ▼                        ▼            │
│   ┌───────────┐            ┌───────────┐            ┌───────────┐       │
│   │ "Describe │            │  Visual   │            │   Code    │       │
│   │  in plain │            │   Flow    │            │    SDK    │       │
│   │  English" │            │  Builder  │            │           │       │
│   └───────────┘            └───────────┘            └───────────┘       │
│         │                         │                        │            │
│   Served by:               Served by:               Served by:          │
│   • Lindy.ai               • Voiceflow              • LangChain         │
│   • OpenAI GPTs            • Cognigy                • CrewAI            │
│   • (Relevance AI)         • Copilot Studio         • Bedrock Agents    │
│                            • n8n                                        │
│                                                                         │
│   GAP: No platform serves ALL THREE with:                               │
│   ├─ Document intelligence built-in                                     │
│   ├─ Enterprise deployment flexibility                                  │
│   └─ Seamless progression from simple → advanced                        │
│                                                                         │
│   ★ ASWA: Full spectrum coverage for all user types                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Comprehensive Feature Comparison

### ASWA vs All Competitors

| Capability | Glean | Dust | Relevance | Lindy | Moveworks | Cognigy | Copilot Studio | **ASWA** |
|------------|:-----:|:----:|:---------:|:-----:|:---------:|:-------:|:--------------:|:--------:|
| **Document Intelligence** |
| Enterprise Search | ★★★★★ | ★★★★☆ | ★★☆☆☆ | ★☆☆☆☆ | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★★★ |
| Multi-doc Reasoning | ★★★☆☆ | ★★★☆☆ | ★☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★☆☆☆☆ | ★★☆☆☆ | ★★★★★ |
| Entity Extraction | ★★★☆☆ | ★★☆☆☆ | ★★☆☆☆ | ☆☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ |
| **Agent Capabilities** |
| Autonomous Agents | ☆☆☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ |
| Multi-Agent | ☆☆☆☆☆ | ★☆☆☆☆ | ★★★★☆ | ★★★★☆ | ☆☆☆☆☆ | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ |
| Action Execution | ☆☆☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★★ |
| **Agent Creation** |
| NLP/Natural Language | ☆☆☆☆☆ | ★★★☆☆ | ★★★★☆ | ★★★★★ | ☆☆☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★★★ |
| Visual Flow Builder | ☆☆☆☆☆ | ★★☆☆☆ | ★★★★☆ | ★★☆☆☆ | ☆☆☆☆☆ | ★★★★★ | ★★★★☆ | ★★★★★ |
| Pre-built Templates | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ |
| Code SDK | ☆☆☆☆☆ | ★★★☆☆ | ★★★☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ |
| **Deployment** |
| SaaS | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| Private Cloud | ★★☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★☆☆☆ | ★★★★★ | ★★★★☆ | ★★★★★ |
| On-Premise | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★★ | ☆☆☆☆☆ | ★★★★★ |
| Air-Gap | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★★ | ☆☆☆☆☆ | ★★★★★ |
| BYOLLM | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★☆☆ | ☆☆☆☆☆ | ★★★★★ |
| **Enterprise** |
| SOC 2 | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| HIPAA | ★★★☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★★★ |
| FedRAMP | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ☆☆☆☆☆ | ★★★★★ | ★★★★☆ |
| Human-in-Loop | ★★☆☆☆ | ★★☆☆☆ | ★★★☆☆ | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ |
| Audit Trail | ★★★☆☆ | ★★☆☆☆ | ★★☆☆☆ | ★☆☆☆☆ | ★★★★☆ | ★★★★★ | ★★★★☆ | ★★★★★ |

---

## Market Gaps & ASWA Opportunity

### Gap Analysis

| Gap | Description | Who Has It | Who Needs It | ASWA Advantage |
|-----|-------------|------------|--------------|----------------|
| **Documents + Agents** | Unified platform for doc intelligence + autonomous agents | Nobody fully | All enterprise | Core differentiation |
| **NLP Agent Creation** | Create agents by describing in plain English | Lindy (consumer), Relevance (SMB) | Enterprise | Enterprise-grade NLP builder |
| **On-Prem AI Agents** | Full on-premise agent platform | Cognigy (conversational only) | Gov, Healthcare, Finance | Full agent platform on-prem |
| **Multi-Doc Reasoning** | Agents that synthesize across document collections | Limited | Legal, Research, Compliance | Built on ASWA's doc intelligence |
| **Vertical Agents** | Pre-built agents for specific industries | None | Healthcare, Legal, Finance | Domain-specific templates |
| **Agent Governance** | Enterprise-grade approval, audit, rollback | Limited | All regulated industries | Human-in-loop + full audit |

### ASWA Unique Position

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ASWA COMPETITIVE POSITIONING                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         DOCUMENT INTELLIGENCE                           │
│                               ▲                                         │
│                               │                                         │
│                    Glean ●    │                                         │
│                  Dust.tt ●    │    ● ASWA (Target)                      │
│                               │         │                               │
│                               │         │ Only platform                 │
│                               │         │ combining all three           │
│                               │         ▼                               │
│  DEPLOYMENT ◄─────────────────┼───────────────────────► AGENT          │
│  FLEXIBILITY                  │                         CREATION        │
│                               │                                         │
│       Cognigy ●               │              ● Relevance AI             │
│       Kore.ai ●               │              ● Lindy.ai                 │
│                               │                                         │
│                               │                                         │
│                    Moveworks ●│● Workato                                │
│                               │                                         │
│                         WORKFLOW AUTOMATION                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Strategic Recommendations

### 1. Product Positioning

**Tagline Options**:
- "Document Intelligence + AI Agents. Deployed Anywhere."
- "From Insights to Actions. Your Data, Your Infrastructure."
- "The Enterprise AI Platform That Does, Not Just Searches."

**Key Messages**:
1. **vs Glean**: "ASWA doesn't just find information—it acts on it"
2. **vs Relevance AI**: "Enterprise-grade with deployment flexibility and document intelligence"
3. **vs Moveworks**: "Not just IT—agents for every department, any document"
4. **vs Microsoft**: "No lock-in—works with any cloud, any LLM, any infrastructure"

### 2. Go-To-Market Priority

| Segment | Priority | Why | Key Feature |
|---------|----------|-----|-------------|
| **Healthcare** | P1 | On-prem required, high doc volume | HIPAA + On-prem + Clinical doc agents |
| **Financial Services** | P1 | Compliance needs, high-value docs | Audit trail + Contract agents |
| **US Government** | P1 | Blocked by all competitors | FedRAMP + Air-gap + BYOLLM |
| **Legal** | P2 | Document-heavy, high margins | Multi-doc reasoning + Contract review |
| **Tech Enterprise** | P2 | Early adopters, reference customers | Full platform capabilities |

### 3. Competitive Moats

| Moat | Description | How to Build |
|------|-------------|--------------|
| **Document Intelligence** | Best multi-document understanding | Invest in parsing, entity extraction, cross-doc reasoning |
| **Deployment Flexibility** | Only full-featured platform with on-prem | Kubernetes-native, BYOLLM support |
| **Agent Templates** | Industry-specific pre-built agents | Partner with domain experts, customers |
| **Agent Marketplace** | Community-created agents | Platform + revenue share |
| **Human-in-Loop UX** | Best approval/governance experience | First-class approval workflows |

### 4. Pricing Strategy

| Tier | Target | Price | vs Competition |
|------|--------|-------|----------------|
| **Starter** | SMB, 50-200 users | $12/user/mo | Cheaper than Glean ($15), more than Dust ($29 flat) |
| **Professional** | Mid-market | $20/user/mo | Agent builder + integrations |
| **Enterprise** | Large orgs | $30/user/mo | Full deployment options + support |
| **Government** | Gov/Defense | Custom | Only option with FedRAMP + air-gap |

**Competitive Pricing Comparison**:
- Glean: $10-15/user (but no agents, no on-prem)
- Relevance AI: ~$99-499/mo flat (not enterprise)
- Cognigy: $100K+/year (conversational only)
- Microsoft Copilot: $30/user (lock-in, no on-prem)

---

## Conclusion

The enterprise AI market is fragmenting into specialized tools:
- **Glean** owns search but can't act
- **Relevance AI** owns no-code agents but lacks documents and enterprise features
- **Cognigy** owns deployment flexibility but focuses on contact centers
- **Microsoft** owns enterprise relationships but locks customers in

**ASWA's opportunity** is to be the **unified platform** that combines:
1. Best-in-class document intelligence
2. User-created AI agents (NLP to pro-code)
3. Full deployment flexibility (SaaS to air-gap)
4. Enterprise governance and compliance

No competitor offers all four. This is the gap.

---

## Appendix: Startup Funding Summary

| Company | Category | Funding | Valuation | Founded |
|---------|----------|---------|-----------|---------|
| Glean | Search | $200M+ | $4.6B | 2019 |
| Moveworks | IT Automation | $200M+ | $2.1B | 2016 |
| Workato | Automation | $290M+ | $5.7B | 2013 |
| Cognigy | Conversational AI | $100M+ | $1.5B | 2016 |
| Lindy.ai | Personal Agents | $50M+ | - | 2022 |
| Adept AI | Foundation Agent | $415M+ | $1B+ | 2022 |
| CrewAI | Multi-Agent | $18M | - | 2023 |
| Relevance AI | Agent Platform | $18M | - | 2020 |
| Dust.tt | AI Assistants | $16M | - | 2022 |
| Botpress | Open Source Conv | $22M | - | 2016 |
| Voiceflow | Conv Design | $20M+ | - | 2019 |
| n8n | Open Source Auto | $12M | - | 2019 |

---

*Analysis Date: January 2026*
*Version: 2.0 (Comprehensive Rewrite)*
