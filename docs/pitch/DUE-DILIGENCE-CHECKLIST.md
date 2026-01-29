# Luemyn - Due Diligence Preparation Checklist

## Overview

This document outlines the materials investors typically request during due diligence. Prepare these documents before starting fundraising to accelerate the process.

---

## Tier 1: Essential (Prepare Before First Meeting)

### Company Formation

- [ ] **Certificate of Incorporation** (Delaware C-Corp recommended)
- [ ] **Bylaws** (current, signed copy)
- [ ] **Stockholder Agreement** (if any)
- [ ] **Board Consents/Resolutions** (since formation)
- [ ] **Cap Table** (clean, updated, include all options)
- [ ] **Stock Option Plan** (409A-compliant)
- [ ] **83(b) Elections** (for founders who filed)
- [ ] **State Qualifications** (if operating in multiple states)

### Intellectual Property

- [ ] **IP Assignment Agreements** (all founders and employees signed)
- [ ] **Patent Applications** (if any filed or planned)
- [ ] **Trademark Registrations** (company name, product names)
- [ ] **Domain Ownership** (proof of ownership for key domains)
- [ ] **Open Source Audit** (list of open source in codebase with licenses)
- [ ] **Software License Agreements** (any third-party software)

### Financials

- [ ] **Historical Financials** (P&L, Balance Sheet - since inception)
- [ ] **Current Bank Statements** (last 3-6 months)
- [ ] **Projections** (3-5 year model with assumptions)
- [ ] **Monthly Burn Rate** (detailed breakdown)
- [ ] **Revenue Breakdown** (by customer, by product, by contract type)

### Team

- [ ] **Founder Backgrounds** (LinkedIn profiles, bios)
- [ ] **Org Chart** (current)
- [ ] **Key Employee Contracts** (especially founders)
- [ ] **Advisor Agreements** (any formal advisors)
- [ ] **Hiring Plan** (next 12-18 months)

---

## Tier 2: Standard DD (Prepare Before Term Sheet)

### Customer & Sales

- [ ] **Customer List** (company names, contract values, start dates)
- [ ] **Sample Contracts** (anonymized if needed)
- [ ] **Sales Pipeline** (stages, values, expected close dates)
- [ ] **Churn History** (any lost customers, reasons)
- [ ] **Customer References** (3-5 customers willing to speak to investors)
- [ ] **Case Studies** (at least 1-2 detailed stories)
- [ ] **NPS/Satisfaction Scores** (if collected)

### Product & Technology

- [ ] **Architecture Diagram** (high-level system design)
- [ ] **Security Practices** (document or SOC 2 report if obtained)
- [ ] **Development Roadmap** (next 6-12 months)
- [ ] **Technical Debt Assessment** (honest evaluation)
- [ ] **Dependency Audit** (key third-party dependencies)
- [ ] **Disaster Recovery Plan** (especially for enterprise customers)
- [ ] **SLA Commitments** (what you promise to customers)

### Legal & Compliance

- [ ] **Material Contracts** (any significant agreements)
- [ ] **Pending Litigation** (or confirmation of none)
- [ ] **Regulatory Compliance** (industry-specific requirements)
- [ ] **Privacy Policy** (current, published)
- [ ] **Terms of Service** (current, published)
- [ ] **Insurance Policies** (D&O, E&O if obtained)
- [ ] **Data Processing Agreements** (GDPR compliance if applicable)

### Employment

- [ ] **Employee Roster** (names, titles, start dates, equity)
- [ ] **Standard Employment Agreement** (template)
- [ ] **Contractor Agreements** (if using contractors)
- [ ] **Employee Handbook** (if exists)
- [ ] **Non-Compete/Non-Solicit** (terms in agreements)
- [ ] **Benefits Summary** (health, 401k, etc.)

---

## Tier 3: Deep Dive (May Be Requested for Series A+)

### Technical Deep Dive

- [ ] **Code Quality Metrics** (test coverage, code review practices)
- [ ] **Uptime History** (SLA performance)
- [ ] **Security Audit** (penetration test results if done)
- [ ] **Scalability Analysis** (how system handles 10x, 100x load)
- [ ] **AI/ML Evaluation** (model performance, training data sourcing)
- [ ] **Vendor Evaluation** (AWS, LLM providers, key dependencies)

### Financial Deep Dive

- [ ] **Cohort Analysis** (revenue by customer cohort over time)
- [ ] **Unit Economics by Segment** (by customer size, industry, etc.)
- [ ] **Accounts Receivable Aging** (customer payment history)
- [ ] **Deferred Revenue Analysis** (recognition schedule)
- [ ] **Tax Returns** (federal and state, all years)
- [ ] **409A Valuation** (most recent, if done)

### Market Analysis

- [ ] **Competitive Landscape** (detailed analysis)
- [ ] **Win/Loss Analysis** (why deals won or lost)
- [ ] **Market Research** (third-party reports, internal analysis)
- [ ] **Customer Interview Summaries** (anonymized insights)
- [ ] **Total Addressable Market Bottoms-Up** (detailed calculation)

---

## Cap Table Best Practices

### Structure Checklist

- [ ] All equity recorded in stock ledger
- [ ] All option grants board-approved
- [ ] Option pool is sufficient (15-20% for Seed, 10-15% for Series A)
- [ ] No unusual provisions (participating preferred, ratchets from prior rounds)
- [ ] Clean ownership (no disputes, no missing signatures)
- [ ] All promises documented (advisor equity, employee grants)

### Common Issues to Fix

| Issue | How to Fix | Priority |
|-------|------------|----------|
| Missing IP assignments | Have all employees/founders sign CIIAA | Critical |
| Founder vesting incomplete | Formalize with board approval | Critical |
| 83(b) elections missing | Cannot retroactively file - document status | High |
| Cap table discrepancies | Reconcile with legal counsel | High |
| Unsigned stock certificates | Obtain signatures immediately | Medium |
| Informal advisor agreements | Convert to formal advisory agreements | Medium |

---

## Data Room Organization

### Recommended Structure

```
/01-Corporate
  /Formation
    - Certificate of Incorporation.pdf
    - Bylaws.pdf
    - Stockholder Agreement.pdf
  /Board
    - Board Consents (chronological)
    - Board Meeting Minutes
  /Cap Table
    - Current Cap Table.xlsx
    - Option Ledger.xlsx
    - 409A Valuation.pdf

/02-Financial
  /Historical
    - P&L by Month.xlsx
    - Balance Sheet.xlsx
    - Bank Statements/
  /Projections
    - Financial Model.xlsx
    - Assumptions.pdf
  /Tax
    - Tax Returns by Year/

/03-Legal
  /Contracts
    - Customer Contracts/
    - Vendor Contracts/
    - Employment Agreements/
  /IP
    - IP Assignment Agreements/
    - Patent Applications/
    - Trademark Registrations/
  /Compliance
    - Privacy Policy.pdf
    - Terms of Service.pdf
    - SOC 2 Report.pdf

/04-Team
  - Org Chart.pdf
  - Founder Bios.pdf
  - Hiring Plan.xlsx
  - Employee Roster.xlsx

/05-Product
  - Architecture Diagram.pdf
  - Roadmap.pdf
  - Security Documentation/
  - Open Source Audit.pdf

/06-Customers
  - Customer List.xlsx
  - Case Studies/
  - Sample Contracts/
  - References.pdf

/07-Market
  - Competitive Analysis.pdf
  - Market Size Analysis.pdf
  - Customer Research/
```

### Data Room Tools

Recommended platforms (support permissions, watermarking, analytics):
- Carta (also handles cap table)
- DocSend
- Dropbox DataRoom
- Google Drive (basic, free)

---

## Reference Check Preparation

### Customer References

Prepare 3-5 customers who can speak to:
- Why they chose Luemyn
- Implementation experience
- ROI/value delivered
- Relationship with team
- Willingness to expand

**Reference Brief Template:**

```
Customer: [Company Name]
Contact: [Name, Title, Email]
Relationship since: [Date]
Contract value: [$X ACV]
Use case: [What they use Luemyn for]
Key wins: [Specific results/metrics]
Notes for call: [Anything to mention or avoid]
```

### Team References

Investors may do backchannel checks on founders. Consider:
- Previous employers who will speak positively
- Co-investors or board members from prior companies
- Colleagues who've worked closely with you

### Proactive vs. Reactive

- **Proactive references**: People you suggest. Prepare them.
- **Backchannel references**: People they find on their own. Nothing you can do, but be aware.

---

## Legal Preparation

### Must-Have Documents Before Fundraising

| Document | Why It Matters | How to Get |
|----------|----------------|------------|
| Delaware C-Corp | Standard for VC investment | Incorporate via Clerky, Stripe Atlas, or lawyer |
| 83(b) Elections | Tax efficiency for founders | File within 30 days of restricted stock grant |
| IP Assignment | Proves company owns all code | Standard CIIAA for all employees/contractors |
| Cap Table | Clean ownership picture | Use Carta, Pulley, or spreadsheet |
| Option Plan | Enable employee grants | 409A valuation required before grants |
| Employment Agreements | Protect company | At-will employment with IP assignment |

### Legal Counsel

Recommended firms for early-stage:
- Cooley
- Wilson Sonsini
- Gunderson Dettmer
- Fenwick & West
- Orrick

Many offer deferred fees for seed-stage companies.

---

## Timeline for DD Preparation

### 8 Weeks Before Fundraising

- [ ] Incorporate properly (Delaware C-Corp)
- [ ] Get IP assignments signed by all team members
- [ ] Clean up cap table
- [ ] Prepare pitch deck
- [ ] Build financial model

### 4 Weeks Before

- [ ] Organize data room
- [ ] Prepare customer references
- [ ] Write case studies
- [ ] Create product architecture doc
- [ ] Gather all contracts

### 2 Weeks Before

- [ ] Final review of all materials
- [ ] Brief customer references
- [ ] Update financials to current month
- [ ] Test data room access
- [ ] Prepare founder stories (backgrounds, why this company)

### During Fundraising

- [ ] Respond to DD requests within 24-48 hours
- [ ] Track what each investor has requested/received
- [ ] Update materials as new data becomes available
- [ ] Keep backup copies of everything

---

## Common DD Red Flags (Avoid These)

### Corporate

- Cap table discrepancies
- Missing founder vesting
- Informal equity promises not documented
- IP ownership unclear
- Delaware incorporation not complete

### Financial

- Numbers don't tie between documents
- Unclear revenue recognition
- Missing or inconsistent data
- Projections wildly disconnected from current trajectory
- Burn rate unclear

### Team

- Founder conflict (current or past)
- Key employees without agreements
- IP assignments missing
- Unusual departure of early employees
- References who don't call back

### Legal

- Outstanding litigation
- Regulatory compliance gaps
- Customer contract issues
- Privacy violations
- Incomplete documentation

---

## DD Process Tips

### Speed Matters

- Investors lose enthusiasm if DD drags
- Prepare materials BEFORE you start fundraising
- Respond to requests same-day when possible

### Be Honest

- Investors will find issues; don't hide them
- Better to proactively disclose than be discovered
- Every company has warts; how you handle them matters

### Stay Organized

- Use consistent naming conventions
- Keep a log of what's been shared with whom
- Have one person responsible for DD responses

### Know Your Materials

- Be able to explain every document
- Know the numbers cold
- Anticipate follow-up questions

---

*Due Diligence Checklist Version: 1.0*
*Last Updated: January 2026*
