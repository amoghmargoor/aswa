# Luemyn - Demo Script

## Demo Overview

**Duration**: 15-20 minutes (adjustable based on audience)

**Audience Variations**:
- **Investor Demo**: Focus on market, differentiation, traction (15 min)
- **Customer Demo**: Focus on pain points, ROI, implementation (20 min)
- **Technical Demo**: Focus on architecture, security, integrations (25 min)

---

## Pre-Demo Checklist

- [ ] Demo environment is running and tested
- [ ] Sample COBOL codebase loaded
- [ ] Sample documents ingested (Jira, Confluence, Slack)
- [ ] Slack workspace connected for live notifications
- [ ] Browser tabs pre-loaded (no login screens during demo)
- [ ] Backup screenshots/video in case of technical issues

---

## Demo Flow

### Act 1: The Problem (3 minutes)

**[Slide: The Legacy Crisis]**

"Before I show you the product, let me set the stage.

**Show statistic slide:**
- 220 billion lines of COBOL in production
- 95% of ATM transactions run on COBOL
- Average COBOL developer: 55+ years old

Every major bank, insurance company, and government agency runs on code written before most of us were born. And the people who understand it are retiring.

**Show failed project examples:**
$300 billion is spent annually on modernization. 70% of projects fail or significantly overrun.

Why? Let me show you..."

---

### Act 2: The Context Problem (2 minutes)

**[Show COBOL code on screen]**

"Here's a real COBOL program from [anonymized customer]. This is `CALC-INTEREST-RATE`.

**Highlight a magic number:**
Notice this: `MULTIPLY RATE BY 1.005`.

A traditional transpiler converts this perfectly to Java. The math is correct. Tests pass. Everyone celebrates.

**Show the failure scenario:**
Six months later, an auditor asks: 'Why 1.005? Where's the documentation for this 0.5% addition?'

The answer isn't in the code. It's here..."

**[Switch to document view - show Jira ticket]**

"JIRA-2847, from 2015: 'Added 0.5% per OCC Bulletin 2015-03'.

And here..."

**[Show Confluence page]**

"A compliance document explaining Reg Z Section 4.2.

And here..."

**[Show Slack thread]**

"A Slack conversation where the auditor said 'we check this quarterly'.

**The insight:**
The code is only half the story. The other half lives in documents that no modernization tool can access.

Until now."

---

### Act 3: Luemyn Code - Understanding Legacy (4 minutes)

**[Open VS Code with Luemyn extension]**

"This is Luemyn Code, running as a VS Code extension.

**Hover over COBOL function:**
When I hover over `CALC-INTEREST-RATE`, I don't just see syntax. I see context.

**Show context panel:**
- Purpose: Reg Z interest calculation with 0.5% compliance adjustment
- Source: JIRA-2847, OCC Bulletin 2015-03
- Last modified: 2015-03-22
- Dependencies: Must run after DAILY-BALANCE
- Warning: Audited quarterly—document all changes

**Ask a question in the IDE:**
Let me ask: 'Why does this add 0.5%?'

**Show AI response:**
'The 0.5% addition was implemented in 2015 to comply with OCC Bulletin 2015-03, which requires a specific adjustment for Regulation Z calculations. Reference: JIRA-2847, compliance-requirements.pdf section 4.2.'

**Key point:**
This isn't ChatGPT making things up. This is grounded in YOUR documents. Every claim has a citation."

---

### Act 4: Luemyn Code - Conversion (3 minutes)

**[Initiate conversion]**

"Now let's convert this to Java.

**Click 'Convert to Java':**

**Show the generated code:**
```java
/**
 * Interest Rate Calculation
 *
 * COMPLIANCE NOTE: Includes 0.5% adjustment per OCC Bulletin 2015-03
 * Required for Regulation Z section 4.2 compliance
 * Reference: JIRA-2847
 *
 * AUDIT: This calculation is reviewed quarterly. Document all changes.
 */
public BigDecimal calculateInterestRate(BigDecimal principal, BigDecimal rate) {
    BigDecimal complianceAdjustment = new BigDecimal("1.005");
    return principal.multiply(rate).multiply(complianceAdjustment);
}
```

**Highlight the difference:**
See what happened? The code isn't just syntactically correct—it's documented. Comments explain WHY. Audit requirements are preserved.

**Show test generation:**
We also generated test cases based on the original COBOL behavior.

**Show validation:**
And here's the validation report showing functional equivalence.

The auditor's question? Already answered in the code."

---

### Act 5: ASWA Platform - Document Intelligence (3 minutes)

**[Switch to ASWA web dashboard]**

"Luemyn Code gets its context from the ASWA Platform.

**Show dashboard overview:**
We've ingested [X] documents across Jira, Confluence, Slack, and file uploads.

**Show search:**
Let me search: 'What are our compliance requirements for interest calculations?'

**Show results with citations:**
Multiple sources, ranked by relevance, with citations.

**Show entity graph:**
We also build an entity graph—who knows what, who owns what, how things relate.

**Click on a person:**
If I click on [name], I can see: 'Expert in: Reg Z compliance, interest calculations. Contact for: audit questions.'"

---

### Act 6: ASWA Platform - Agent Builder (3 minutes)

**[Navigate to Agent Builder]**

"But ASWA isn't just for search. Users can create their own AI agents.

**Show agent creation:**
I'll type: 'When a new customer support email comes in, summarize the issue, check our knowledge base for similar problems, and create a Zendesk ticket with priority based on customer tier.'

**Click Generate:**

**Show generated agent:**
- Trigger: Email received
- Actions: Summarize, Search KB, Lookup CRM, Create Ticket
- Conditions: Enterprise customer → notify #support-escalations

**Show approval settings:**
Notice it defaults to 'review mode'—the agent suggests actions, a human approves.

**Show testing:**
Let me test with a sample email...

**Show test results:**
Summary, KB matches, proposed ticket. All before anything is executed.

**The power:**
Non-developers just created an AI workflow. No code required."

---

### Act 7: Deployment Flexibility (2 minutes)

**[Show architecture diagram]**

"One more thing that matters for enterprise.

**Show deployment options:**
This entire platform—Luemyn Code, ASWA, everything—runs identically:
- In our cloud (SaaS)
- In your AWS/Azure/GCP (private cloud)
- In your data center (on-premise)
- Without internet access (air-gapped)

**Why it matters:**
Banks can't send COBOL to ChatGPT. Government agencies can't put classified docs in the cloud.

We're the only platform with this flexibility.

**Show BYOLLM:**
You can even bring your own LLM. Use Claude, GPT-4, Llama, or any model you've approved.

**The bottom line:**
Your data, your infrastructure, your AI policy."

---

### Act 8: Closing (2 minutes)

**[Return to summary slide]**

"Let me summarize what you just saw:

1. **The Problem**: Legacy modernization fails because tools understand code, not context.

2. **Luemyn Code**: A coding agent that understands COBOL AND pulls context from documents.

3. **ASWA Platform**: Document intelligence that anyone can search, plus an agent builder for custom automation.

4. **Deployment**: Runs anywhere—SaaS to air-gapped.

**For investors:**
This is the enterprise AI platform for regulated industries. $300B market, 70% failure rate, and we're the only solution that addresses the real problem.

**For customers:**
You've tried manual modernization. You've tried transpilers. They don't work because they don't understand context. We do.

**Questions?**"

---

## Backup Demos (if time or interest)

### Backup A: Batch Conversion Workflow
Show the workflow interface for converting entire modules:
- Import COBOL source
- Analysis phase (dependencies, complexity)
- Conversion queue with progress
- Validation reports
- Human review checkpoints

### Backup B: Integration Deep Dive
Show specific integrations:
- Jira bidirectional sync (tickets ↔ code changes)
- Slack bot for queries
- Confluence page generation
- Webhook delivery for events

### Backup C: Admin & Security
Show enterprise features:
- Tenant management
- RBAC configuration
- Audit logs
- SSO setup
- PII detection and masking

---

## Handling Common Demo Objections

### "Can it handle our specific COBOL dialect?"

"We support all major COBOL dialects—IBM Enterprise COBOL, Micro Focus, ACUCOBOL. During pilot, we'll validate against your specific codebase and handle any dialect-specific constructs."

### "What about RPG/PL/I/Natural?"

"RPG and PL/I are on our roadmap. [If relevant: We have early support for X.] Our architecture is language-agnostic—adding new languages is an engineering effort, not an architecture change."

### "How accurate is the conversion?"

"We target 80%+ automated conversion with human review for the rest. We're not trying to replace developers—we're making them 10x more productive. Every conversion goes through validation and testing before deployment."

### "What if the AI hallucinates?"

"Three safeguards: (1) All claims are grounded in your documents—we show citations. (2) Conversion runs through automated validation against original behavior. (3) Human-in-the-loop review for critical changes. We assume the AI isn't perfect; the architecture handles that."

### "How long does implementation take?"

"Typical pilot: 4-6 weeks. This includes document ingestion, integration setup, and initial conversions. We work alongside your team, not as a black box."

### "What's the pricing?"

"Platform subscription plus usage-based conversion pricing. Roughly: $30/user/month for the platform, $50-100/developer/month for Luemyn Code, plus per-line fees for batch conversion. On-premise is 2x cloud pricing. Happy to discuss specifics for your situation."

---

## Post-Demo Follow-up

Send within 24 hours:
- [ ] Thank you email
- [ ] Deck with demo screenshots
- [ ] Relevant case study or reference
- [ ] Specific next steps (pilot proposal, technical deep dive, etc.)
- [ ] Calendar link for follow-up call

---

*Demo Script Version: 1.0*
*Last Updated: January 2026*
