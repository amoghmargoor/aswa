# Luemyn - Investor FAQ

## The Hard Questions VCs Will Ask

This document prepares founders for tough investor questions with suggested responses.

---

## Product & Technology

### "Why can't enterprises just use ChatGPT/Claude directly?"

**Answer:**
Three critical gaps make consumer AI unusable for enterprise legacy modernization:

1. **Data Residency**: 70% of our target customers (banks, government) legally cannot send data to cloud AI. ChatGPT and Claude are SaaS-only. We deploy on-premise and air-gapped.

2. **Legacy Code Understanding**: General-purpose LLMs weren't trained on COBOL, RPG, or JCL. They hallucinate when asked to convert it. We've built specialized parsing and understanding for legacy languages.

3. **Institutional Context**: An LLM can't know that your `CALC-INTEREST-RATE` function exists because of OCC Bulletin 2015-03. Our platform connects code to the documents that explain it.

---

### "How is this different from Glean?"

**Answer:**
Glean is read-only enterprise search. We're action-oriented with agents.

| Capability | Glean | Luemyn |
|------------|-------|--------|
| Find documents | Yes | Yes |
| Create tickets from insights | No | Yes |
| Convert COBOL to Java | No | Yes |
| Deploy on-premise | No | Yes |
| User-created AI agents | No | Yes |

Glean helps you find information. Luemyn helps you act on it.

---

### "Why not use existing modernization tools like Micro Focus or Modern Systems?"

**Answer:**
They're pattern-matching transpilers, not AI. They convert syntax, not semantics.

Example: A COBOL program adds 0.5% to a calculation. A transpiler converts the math perfectly to Java. But it doesn't know that 0.5% exists because of a 2015 regulatory requirement—so the Java code has no comments, no audit trail, and fails the next compliance review.

Luemyn Code + ASWA Platform understands both the code AND the institutional knowledge around it.

---

### "What's your technical moat?"

**Answer:**
Four layers of defensibility:

1. **Legacy Language Models**: Fine-tuned models for COBOL/RPG/PL/I that outperform general LLMs on legacy code tasks.

2. **Code-Document Linking**: Proprietary approach to connecting code artifacts with business documentation (the "why" behind the "what").

3. **Deployment Architecture**: Kubernetes-native platform that runs identically from SaaS to air-gapped environments—competitors can't easily retrofit this.

4. **Agent Platform Network Effects**: As customers build and share agents, the platform becomes more valuable.

---

### "How do you handle hallucinations in code conversion?"

**Answer:**
We don't trust the AI to be perfect. Our architecture assumes errors:

1. **Verification Pipeline**: Every conversion runs through automated testing against the original behavior.

2. **Human-in-the-Loop**: Critical conversions require human approval before deployment.

3. **Incremental Migration**: We don't convert entire systems at once—we convert function-by-function with validation.

4. **Rollback Capability**: Every conversion is reversible with full audit trail.

The key insight: we use AI to accelerate developers, not replace them. A 10x speedup with human oversight is better than 100x with undetected errors.

---

## Market & Competition

### "The legacy modernization market seems crowded. Why will you win?"

**Answer:**
It's crowded with services companies (Accenture, TCS, Infosys) who charge millions for multi-year projects with 70% failure rates.

The software market is actually underserved:
- **Micro Focus**: Legacy tools, no AI
- **Modern Systems**: Pattern matching, no context
- **AWS Mainframe Modernization**: Rehosting, not conversion

We're the first platform combining:
- AI-powered code understanding
- Document intelligence for context
- User-created agents for automation
- Full deployment flexibility

---

### "Who's your real competition?"

**Answer:**
**Short-term**: Internal teams trying to do this themselves. Our competition is the "build it in-house" decision.

**Medium-term**: Accenture/Deloitte could build or acquire similar capabilities. Our advantage is speed and focus—we're shipping features while they're forming committees.

**Long-term**: Anthropic/OpenAI could add enterprise features. But they won't go on-premise, won't specialize in COBOL, and won't build vertical solutions. They're horizontal platforms.

---

### "Why now? COBOL modernization has been a thing for 30 years."

**Answer:**
Three converging factors create urgency:

1. **Workforce Crisis**: Average COBOL developer is 55+. Mass retirements are happening NOW. Companies can't wait.

2. **AI Capability Inflection**: LLMs can finally understand code semantically. This wasn't possible 3 years ago.

3. **Cloud AI Backlash**: Enterprises tried ChatGPT, hit data sovereignty walls. They're actively looking for on-premise alternatives.

The $300B modernization market exists. The 70% failure rate exists. What's new is that AI finally makes success possible.

---

### "What's the regulatory environment look like?"

**Answer:**
Regulatory pressure is accelerating modernization:

- **DORA (EU)**: Digital Operational Resilience Act requires banks to modernize critical systems.
- **OCC Guidance**: US banking regulators pushing for mainframe risk reduction.
- **FedRAMP Requirements**: Government agencies need certified platforms for AI adoption.

We're building toward FedRAMP certification precisely because regulatory requirements create demand for compliant platforms.

---

## Business Model

### "Walk me through your unit economics."

**Answer:**
**Target Customer Profile**:
- Fortune 500 bank or insurance company
- 10-50M lines of COBOL
- Active modernization initiative
- IT budget: $100M+

**Pricing**:
- Platform: $30/user/month (100+ users typical)
- Luemyn Code: $50-100/developer/month
- Conversion Volume: Per-1000-lines pricing
- On-Premise Premium: 2x cloud pricing

**Target Unit Economics**:
- ACV: $250K - $2M
- Gross Margin: 75-80%
- CAC Payback: 18 months
- Net Revenue Retention: 120%+ (expand within accounts)
- LTV/CAC: 5x+

---

### "How long is your sales cycle?"

**Answer:**
Enterprise sales: 6-12 months for initial deployment.

Our approach to shorten it:
1. **Pilot-First**: Start with $50-100K pilot on specific use case
2. **Quick Win**: Demonstrate value in 30-60 days
3. **Expand**: Grow to full deployment ($500K-2M)

We're not trying to sell enterprise-wide from day one. We land and expand.

---

### "What's your CAC look like?"

**Answer:**
Early stage, so still calibrating. Expected range:

- **Direct Sales CAC**: $50-100K (including salary, marketing, travel)
- **Partner-Sourced CAC**: $25-50K (SI partners bring deals)

Target is 18-month payback on CAC, which is reasonable for enterprise software with high retention.

---

### "How do you think about pricing power?"

**Answer:**
High pricing power due to:

1. **Switching Costs**: Custom agents and document integrations create stickiness
2. **Mission Critical**: Code conversion is high-stakes, not commodity
3. **Limited Alternatives**: No comparable on-premise AI platform exists
4. **Value-Based Pricing**: Savings vs. Accenture projects are 10x+

We can charge 2x for on-premise because it's the only option for regulated industries.

---

## Go-to-Market

### "Who's your ideal first customer?"

**Answer:**
**Profile**:
- Fortune 500 bank or insurance company
- 10-50 million lines of COBOL in production
- Active, funded modernization initiative (not "exploring")
- CIO/CTO sponsor who's been burned by failed projects before
- Open to on-premise deployment

**Why**: They have budget, urgency, and pain from previous failures. They're sophisticated enough to evaluate AI solutions and desperate enough to try something new.

---

### "How do you acquire customers?"

**Answer:**
**Phase 1 (Now)**: Design partner outreach
- Direct outreach to modernization leaders at target accounts
- Warm intros from advisors/investors
- 3-5 design partners at pilot pricing

**Phase 2 (6-12 months)**: Direct sales
- Hire 2-3 enterprise AEs
- Conference presence (Gartner, Forrester events)
- Content marketing (thought leadership on legacy modernization)

**Phase 3 (12+ months)**: Partner channel
- SI partnerships (Accenture, Deloitte, IBM)
- They bring deals, we provide platform
- Revenue share model

---

### "What's your customer acquisition motion?"

**Answer:**
**Outbound-Led Enterprise Sales**:

1. **Identify**: Find companies with active modernization RFPs or public announcements
2. **Multi-Thread**: Reach CIO, VP Modernization, and practitioners simultaneously
3. **Educate**: Thought leadership content on AI-assisted modernization
4. **Pilot**: Propose limited pilot on specific pain point
5. **Prove**: Demonstrate 10x improvement over manual process
6. **Expand**: Grow from pilot to enterprise deployment

We're not doing self-serve. This is high-touch enterprise sales.

---

## Team & Execution

### "Why are you the right team to build this?"

**Answer:**
[Placeholder - founders should customize with their actual backgrounds]

Key elements investors want to see:
- Domain expertise in legacy systems or enterprise software
- Technical depth in AI/ML
- Enterprise sales experience
- Previous startup experience (success or failure)

---

### "What are your key hires in the next 12 months?"

**Answer:**
1. **VP Engineering**: Platform scale and reliability
2. **VP Sales**: Enterprise sales motion
3. **Head of Customer Success**: Design partner support
4. **Security/Compliance Lead**: FedRAMP certification

These roles directly support the milestones: product, revenue, customer success, and certification.

---

### "What's your burn rate and runway?"

**Answer:**
[Placeholder - will depend on funding round]

Pre-raise:
- Team size: X
- Monthly burn: $X
- Current runway: X months

Post-raise (target):
- Team size: X (hiring X)
- Monthly burn: $X
- Runway: 18-24 months

---

## Risks & Challenges

### "What keeps you up at night?"

**Answer:**
Being honest about risks:

1. **Enterprise Sales Cycle**: These deals take 6-12 months. Cash management is critical until we have recurring revenue.

2. **Technical Complexity**: COBOL variants are numerous. Each mainframe environment is different. We need to build robust, not just demo-ready.

3. **Execution Risk**: We're building two products (Luemyn Code + ASWA Platform) simultaneously. Focus is essential.

4. **Team Building**: Enterprise AI requires a unique blend of skills. Finding the right people is hard.

---

### "What if Anthropic or OpenAI goes enterprise?"

**Answer:**
They will go enterprise. Claude Enterprise already exists.

But they won't:
- Go on-premise or air-gapped (fundamentally SaaS businesses)
- Specialize in COBOL/RPG (not their market)
- Build vertical solutions for legacy modernization (horizontal platforms)
- Compete with their customers (we're building on their APIs)

We're complementary, not competitive. We make their models more useful for enterprises that can't use them directly.

---

### "What if a big SI (Accenture, Deloitte) builds this?"

**Answer:**
They could, but likely won't:

1. **Cannibalization**: They make billions on manual modernization projects. A tool that 10x productivity threatens their revenue model.

2. **Software DNA**: They're services companies. Building and maintaining software products requires different skills and incentives.

3. **Speed**: We're shipping features while they're forming committees.

More likely outcome: they become our partners and resellers, not our competitors.

---

### "What's the biggest technical risk?"

**Answer:**
**Accuracy at Scale**: COBOL codebases are massive (10-50M+ lines). Edge cases multiply. Our approach:

- Invest in comprehensive test suites
- Build modular architecture for incremental improvement
- Design for human-in-the-loop from day one
- Target "accelerator" not "replacement"

We're not promising perfect automated conversion. We're promising 10x developer productivity with human oversight.

---

## Vision & Exit

### "What does success look like in 5 years?"

**Answer:**
**Vision**: Luemyn is the default platform for enterprise AI in regulated industries.

**Metrics**:
- $100M+ ARR
- 100+ enterprise customers
- FedRAMP High certified
- SI partner ecosystem
- Agent marketplace with community contributions

**Market Position**: The "Salesforce of Enterprise AI"—horizontal platform that enables vertical solutions.

---

### "What's your exit strategy?"

**Answer:**
We're building to be a standalone company, but realistic exit paths include:

1. **IPO**: At $100M+ ARR with strong growth
2. **Strategic Acquisition**:
   - IBM (mainframe ecosystem)
   - ServiceNow (enterprise workflow)
   - Microsoft (enterprise AI)
   - Private equity rollup of enterprise AI

We're not building to flip. We're building a category-defining company.

---

### "What's your 18-month roadmap?"

**Answer:**
**Milestones to Next Round**:

| Milestone | Target |
|-----------|--------|
| ARR | $2M |
| Enterprise Customers | 10 |
| Design Partners | 3 Fortune 500 |
| Compliance | SOC 2 Type II, HIPAA |
| Team Size | 15-20 |

**Product**:
- Agent builder (NLP + visual)
- COBOL → Java conversion workflow
- On-premise deployment (Helm charts)
- 3+ enterprise connectors

---

## Accelerator-Specific Questions

### "Why apply to [Accelerator Name]?"

**Answer:**
[Customize for each accelerator]

For YC:
- Network access to enterprise buyers
- Credibility with investors for next round
- Tactical advice on enterprise GTM

For enterprise-focused accelerators (Alchemist, Plug and Play):
- Direct customer introductions
- Enterprise sales coaching
- Pilot program access

---

### "How would you use the accelerator resources?"

**Answer:**
1. **Customer Intros**: Priority #1 is design partner acquisition
2. **Investor Network**: Prep for Series A
3. **Founder Network**: Learn from enterprise software builders
4. **Tactical Advice**: Enterprise sales, pricing, hiring

We're not looking for free office space. We're looking for acceleration.

---

### "What would make this accelerator experience a success?"

**Answer:**
Clear success criteria:
- 3+ design partner LOIs signed
- First paying customer
- Series A term sheet discussions started
- Key VP hire (Sales or Engineering)

---

## Closing

### "What's your ask?"

**Answer:**
We're raising $[X]M to:
- Build out the platform (50% of funds)
- Hire enterprise sales team (30% of funds)
- Obtain compliance certifications (15% of funds)
- Operations (5% of funds)

This gets us to $2M ARR and positions us for Series A.

### "Why should we invest now?"

**Answer:**
1. **Timing**: AI capability + workforce crisis + cloud backlash = perfect storm
2. **Team**: [Reference relevant experience]
3. **Market**: $300B TAM with 70% failure rate = room for improvement
4. **Traction**: [Reference any pilots/LOIs]
5. **Terms**: Early stage = best valuation for the risk

The question isn't whether enterprise AI will be big. It's who will own the regulated industries. That's us.

---

*Prepared: January 2026*
*Version: 1.0*
