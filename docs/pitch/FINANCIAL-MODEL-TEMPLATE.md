# Luemyn - Financial Model Template

## Overview

This template provides a framework for building financial projections for investor presentations. All numbers are placeholders - customize with actual data.

---

## Key Assumptions

### Revenue Assumptions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REVENUE MODEL ASSUMPTIONS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ASWA PLATFORM                                                               │
│  ├─ Price per user/month: $30 (enterprise tier)                             │
│  ├─ Average users per customer: 150                                         │
│  ├─ Monthly platform revenue per customer: $4,500                           │
│  └─ Annual platform revenue per customer: $54,000                           │
│                                                                              │
│  LUEMYN CODE                                                                 │
│  ├─ Price per developer/month: $75 (average of tiers)                       │
│  ├─ Average developers per customer: 20                                     │
│  ├─ Monthly Luemyn Code revenue per customer: $1,500                        │
│  └─ Annual Luemyn Code revenue per customer: $18,000                        │
│                                                                              │
│  CONVERSION VOLUME                                                           │
│  ├─ Price per 1,000 lines converted: $100                                   │
│  ├─ Average lines converted per customer (Year 1): 500,000                  │
│  └─ Conversion revenue per customer (Year 1): $50,000                       │
│                                                                              │
│  ON-PREMISE PREMIUM                                                          │
│  ├─ Multiplier: 2x cloud pricing                                            │
│  └─ % of customers on-prem: 60%                                             │
│                                                                              │
│  BLENDED ACV CALCULATION                                                     │
│  ├─ Cloud customer ACV: $122,000                                            │
│  │   └─ ($54K platform + $18K code + $50K conversion)                       │
│  ├─ On-prem customer ACV: $244,000                                          │
│  │   └─ (2x cloud)                                                          │
│  └─ Blended ACV: $195,200                                                   │
│      └─ (40% cloud × $122K + 60% on-prem × $244K)                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Customer Acquisition Assumptions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CUSTOMER ACQUISITION ASSUMPTIONS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SALES CYCLE                                                                 │
│  ├─ Average sales cycle: 6 months                                           │
│  ├─ Pilot duration: 2-3 months                                              │
│  └─ Pilot to paid conversion: 60%                                           │
│                                                                              │
│  SALES PRODUCTIVITY                                                          │
│  ├─ Ramp time for new AE: 6 months                                          │
│  ├─ Quota per ramped AE: $1.2M ARR/year                                     │
│  └─ Quota attainment (blended): 70%                                         │
│                                                                              │
│  CAC COMPONENTS                                                              │
│  ├─ Direct sales CAC: $80,000                                               │
│  │   └─ (AE salary + marketing + travel / deals closed)                     │
│  ├─ Partner-sourced CAC: $40,000                                            │
│  │   └─ (Revenue share + minimal direct cost)                               │
│  └─ Blended CAC: $65,000                                                    │
│      └─ (Assuming 50% partner-sourced at scale)                             │
│                                                                              │
│  RETENTION                                                                   │
│  ├─ Gross logo retention: 95%                                               │
│  ├─ Net revenue retention: 120%                                             │
│  │   └─ (Expansion: more users, more conversion volume)                     │
│  └─ Churn drivers: Budget cuts, project completion                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cost Assumptions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COST ASSUMPTIONS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PEOPLE COSTS                                                                │
│  ├─ Engineering (avg fully loaded): $200,000/year                           │
│  ├─ Sales AE (base + OTE): $250,000/year                                    │
│  ├─ Sales SDR: $100,000/year                                                │
│  ├─ Customer Success: $150,000/year                                         │
│  ├─ G&A (finance, HR, ops): $175,000/year                                   │
│  └─ Executive team: $300,000/year (avg)                                     │
│                                                                              │
│  INFRASTRUCTURE                                                              │
│  ├─ Cloud hosting (per $1 revenue): $0.10                                   │
│  ├─ LLM API costs (per $1 revenue): $0.08                                   │
│  └─ Third-party tools: $5,000/month                                         │
│                                                                              │
│  OTHER COSTS                                                                 │
│  ├─ Legal/compliance: $50,000/year                                          │
│  ├─ Marketing programs: $10,000/month                                       │
│  ├─ Travel: $2,500/AE/month                                                 │
│  └─ Office/equipment: $1,000/employee/month                                 │
│                                                                              │
│  TARGET GROSS MARGIN: 75-80%                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5-Year Revenue Projection

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              5-YEAR REVENUE PROJECTION                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  YEAR                    Y1          Y2          Y3          Y4          Y5         │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  NEW CUSTOMERS                                                                       │
│  ├─ New customers        5          15          35          60          90          │
│  ├─ Churned              0           0           1           3           6          │
│  └─ Ending customers     5          20          54         111         195          │
│                                                                                      │
│  ARR ($ millions)                                                                    │
│  ├─ Beginning ARR       $0.0        $1.0        $4.3       $12.3       $27.2        │
│  ├─ New ARR             $1.0        $2.9        $6.8       $11.7       $17.6        │
│  ├─ Expansion ARR       $0.0        $0.6        $1.6        $4.0        $8.2        │
│  ├─ Churned ARR         $0.0        $0.0       -$0.4       -$0.8       -$1.6        │
│  └─ Ending ARR          $1.0        $4.3       $12.3       $27.2       $51.4        │
│                                                                                      │
│  REVENUE BREAKDOWN                                                                   │
│  ├─ Platform            30%         32%         35%         38%         40%         │
│  ├─ Luemyn Code         25%         25%         25%         25%         25%         │
│  ├─ Conversion          40%         38%         35%         32%         30%         │
│  └─ Services             5%          5%          5%          5%          5%         │
│                                                                                      │
│  KEY METRICS                                                                         │
│  ├─ YoY Growth            -        330%        186%        121%         89%         │
│  ├─ Avg ACV            $195K       $195K       $195K       $195K       $195K        │
│  └─ NRR                   -        120%        120%        118%        115%         │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Headcount Plan

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 HEADCOUNT PLAN                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  DEPARTMENT              Y1          Y2          Y3          Y4          Y5         │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  ENGINEERING                                                                         │
│  ├─ Platform              4           8          14          22          32         │
│  ├─ Luemyn Code           3           6          10          15          20         │
│  ├─ Infrastructure        1           2           4           6           8         │
│  └─ Subtotal              8          16          28          43          60         │
│                                                                                      │
│  SALES & MARKETING                                                                   │
│  ├─ AEs                   2           5          10          18          28         │
│  ├─ SDRs                  2           4           8          12          16         │
│  ├─ Sales leadership      1           2           3           4           5         │
│  ├─ Marketing             1           3           5           8          12         │
│  └─ Subtotal              6          14          26          42          61         │
│                                                                                      │
│  CUSTOMER SUCCESS                                                                    │
│  ├─ CSMs                  1           3           7          14          24         │
│  ├─ Support               1           2           4           8          12         │
│  ├─ Solutions eng         1           2           4           6           8         │
│  └─ Subtotal              3           7          15          28          44         │
│                                                                                      │
│  G&A                                                                                 │
│  ├─ Executive             2           3           4           5           6         │
│  ├─ Finance               1           2           3           5           7         │
│  ├─ HR/recruiting         0           1           2           4           6         │
│  ├─ Legal/compliance      0           1           2           3           4         │
│  └─ Subtotal              3           7          11          17          23         │
│                                                                                      │
│  TOTAL HEADCOUNT         20          44          80         130         188         │
│                                                                                      │
│  RATIOS                                                                              │
│  ├─ Eng as % of total    40%         36%         35%         33%         32%        │
│  ├─ S&M as % of total    30%         32%         33%         32%         32%        │
│  ├─ ARR per employee    $50K        $98K       $154K       $209K       $273K        │
│  └─ Customers per CSM     5           7           8           8           8         │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## P&L Projection

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               P&L PROJECTION ($ millions)                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  LINE ITEM               Y1          Y2          Y3          Y4          Y5         │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  REVENUE                                                                             │
│  ├─ ARR (ending)        $1.0        $4.3       $12.3       $27.2       $51.4        │
│  ├─ Recognized revenue  $0.5        $2.7        $8.3       $19.8       $39.3        │
│  └─ Services            $0.0        $0.1        $0.4        $1.0        $2.0        │
│  TOTAL REVENUE          $0.5        $2.8        $8.7       $20.8       $41.3        │
│                                                                                      │
│  COST OF REVENUE                                                                     │
│  ├─ Infrastructure      $0.1        $0.3        $0.9        $2.1        $4.1        │
│  ├─ LLM API costs       $0.0        $0.2        $0.7        $1.7        $3.3        │
│  ├─ Support costs       $0.2        $0.3        $0.6        $1.2        $1.8        │
│  TOTAL COR              $0.3        $0.8        $2.2        $5.0        $9.2        │
│                                                                                      │
│  GROSS PROFIT           $0.2        $2.0        $6.5       $15.8       $32.1        │
│  GROSS MARGIN           40%         71%         75%         76%         78%         │
│                                                                                      │
│  OPERATING EXPENSES                                                                  │
│  ├─ R&D                 $1.6        $3.2        $5.6        $8.6       $12.0        │
│  ├─ Sales & Marketing   $1.2        $2.8        $5.2        $8.4       $12.2        │
│  ├─ General & Admin     $0.5        $1.2        $1.9        $3.0        $4.0        │
│  TOTAL OPEX             $3.3        $7.2       $12.7       $20.0       $28.2        │
│                                                                                      │
│  OPERATING INCOME      -$3.1       -$5.2       -$6.2       -$4.2        $3.9        │
│  OPERATING MARGIN      -620%       -186%        -71%        -20%          9%        │
│                                                                                      │
│  EBITDA                -$3.0       -$5.0       -$5.8       -$3.8        $4.3        │
│                                                                                      │
│  KEY METRICS                                                                         │
│  ├─ R&D as % revenue    320%        114%         64%         41%         29%        │
│  ├─ S&M as % revenue    240%        100%         60%         40%         30%        │
│  ├─ G&A as % revenue    100%         43%         22%         14%         10%        │
│  └─ Burn multiple        6.2x        1.9x        0.7x        0.2x       (0.1x)      │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Cash Flow & Funding

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            CASH FLOW & FUNDING ($ millions)                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  LINE ITEM               Y1          Y2          Y3          Y4          Y5         │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  CASH FLOW                                                                           │
│  ├─ Operating income   -$3.1       -$5.2       -$6.2       -$4.2        $3.9        │
│  ├─ D&A                 $0.1        $0.2        $0.4        $0.4        $0.4        │
│  ├─ Working capital    -$0.1       -$0.3       -$0.5       -$0.8       -$1.0        │
│  NET CASH FROM OPS     -$3.1       -$5.3       -$6.3       -$4.6        $3.3        │
│                                                                                      │
│  FUNDING                                                                             │
│  ├─ Seed (raised)       $4.0          -           -           -           -         │
│  ├─ Series A              -         $15.0         -           -           -         │
│  ├─ Series B              -           -         $30.0         -           -         │
│  └─ Total raised        $4.0       $19.0       $49.0       $49.0       $49.0        │
│                                                                                      │
│  CASH POSITION                                                                       │
│  ├─ Beginning cash      $0.0        $0.9       $10.6       $34.3       $29.7        │
│  ├─ Cash burn          -$3.1       -$5.3       -$6.3       -$4.6        $3.3        │
│  ├─ Funding             $4.0       $15.0       $30.0         -           -          │
│  └─ Ending cash         $0.9       $10.6       $34.3       $29.7       $33.0        │
│                                                                                      │
│  RUNWAY                                                                              │
│  ├─ Monthly burn       $0.26       $0.44       $0.53       $0.38      ($0.28)       │
│  └─ Months runway        3.5        24.1        64.7        78.2        N/A         │
│                                                                                      │
│  FUNDING MILESTONES                                                                  │
│  ├─ Seed: $4M           MVP + 5 design partners                                     │
│  ├─ Series A: $15M      $2M ARR + 10 customers + SOC2                               │
│  └─ Series B: $30M      $12M ARR + 50 customers + FedRAMP                           │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Unit Economics Summary

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              UNIT ECONOMICS SUMMARY                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  METRIC                  TARGET        CURRENT       BENCHMARK                       │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  REVENUE                                                                             │
│  ├─ ACV                  $195K         [TBD]         $100-300K (enterprise)         │
│  ├─ Gross margin         75-80%        [TBD]         75-85% (SaaS)                  │
│  └─ NRR                  120%          [TBD]         110-130% (enterprise)          │
│                                                                                      │
│  CUSTOMER                                                                            │
│  ├─ CAC                  $65K          [TBD]         $50-100K (enterprise)          │
│  ├─ CAC payback          18 mo         [TBD]         12-24 mo                       │
│  └─ LTV/CAC              5.0x          [TBD]         3-5x (healthy)                 │
│                                                                                      │
│  SALES                                                                               │
│  ├─ Quota per AE         $1.2M         [TBD]         $800K-1.5M                     │
│  ├─ Quota attainment     70%           [TBD]         60-80%                         │
│  └─ Sales cycle          6 mo          [TBD]         6-12 mo (enterprise)           │
│                                                                                      │
│  OPERATIONS                                                                          │
│  ├─ ARR per employee     $200K+        [TBD]         $150-250K (growth stage)       │
│  └─ Rule of 40           40%+          [TBD]         40%+ (healthy)                 │
│                                                                                      │
│  LTV CALCULATION                                                                     │
│  ├─ Annual revenue       $195,000                                                   │
│  ├─ Gross margin         78%                                                        │
│  ├─ Gross profit/year    $152,100                                                   │
│  ├─ Customer lifetime    4 years (75% retention)                                    │
│  └─ LTV                  $325,000                                                   │
│                                                                                      │
│  LTV/CAC = $325K / $65K = 5.0x ✓                                                    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Scenario Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SCENARIO ANALYSIS - Y3 ARR                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  SCENARIO           NEW CUSTOMERS    ACV        NRR        Y3 ARR      PATH TO IPO  │
│  ───────────────────────────────────────────────────────────────────────────────── │
│                                                                                      │
│  BEAR CASE                                                                           │
│  ├─ Assumption      30% fewer        $150K      110%       $7.5M       Longer       │
│  ├─ Drivers         Sales slower,    Pricing    Lower      runway,     Need         │
│  │                  bigger deals     pressure   expansion  pivot?      Series C     │
│  └─ Mitigation      Focus on fewer   Value      Invest in               to reach    │
│                     larger deals     selling    CS team                 $50M        │
│                                                                                      │
│  BASE CASE                                                                           │
│  ├─ Assumption      As modeled       $195K      120%       $12.3M      Y5-Y6        │
│  ├─ Drivers         Plan execution   Market     Strong     Target                   │
│  │                  as expected      rate       product                             │
│  └─ Path            Series A → B →                         $50M+ ARR               │
│                     profitability                          by Y5-6                  │
│                                                                                      │
│  BULL CASE                                                                           │
│  ├─ Assumption      50% more         $250K      130%       $22M        Y4           │
│  ├─ Drivers         Faster sales,    Premium    Platform   Faster                   │
│  │                  strong demand    for value  stickiness profitability            │
│  └─ Upside          May not need                           Path to                  │
│                     Series B                               $100M ARR                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics to Track

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              KEY METRICS DASHBOARD                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WEEKLY                                                                              │
│  ├─ Pipeline value added                                                            │
│  ├─ Demos completed                                                                 │
│  ├─ Pilot starts                                                                    │
│  └─ Support tickets resolved                                                        │
│                                                                                      │
│  MONTHLY                                                                             │
│  ├─ MRR / ARR                                                                       │
│  ├─ New customers                                                                   │
│  ├─ Churn (logo and revenue)                                                        │
│  ├─ CAC (by channel)                                                                │
│  ├─ Burn rate                                                                       │
│  └─ Runway (months)                                                                 │
│                                                                                      │
│  QUARTERLY                                                                           │
│  ├─ NRR                                                                             │
│  ├─ Gross margin                                                                    │
│  ├─ CAC payback                                                                     │
│  ├─ LTV/CAC                                                                         │
│  ├─ ARR per employee                                                                │
│  ├─ Rule of 40 score                                                                │
│  └─ Product usage metrics (DAU, features used)                                      │
│                                                                                      │
│  BOARD MEETING                                                                       │
│  ├─ Revenue vs plan                                                                 │
│  ├─ Customer count vs plan                                                          │
│  ├─ Cash position and runway                                                        │
│  ├─ Key wins and losses                                                             │
│  ├─ Product roadmap progress                                                        │
│  └─ Hiring vs plan                                                                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Investor Presentation Slides (Summary)

When presenting financials, include:

1. **Revenue Model Slide**: How you make money (subscription + usage + premium)
2. **TAM/SAM/SOM Slide**: Market size with bottoms-up analysis
3. **Unit Economics Slide**: CAC, LTV, payback, NRR
4. **Growth Trajectory Slide**: 5-year revenue projection
5. **Use of Funds Slide**: How you'll spend the raise
6. **Milestones to Next Round Slide**: What you'll achieve

---

## Notes for Customization

1. **Replace all placeholders** with actual data before presenting
2. **Validate assumptions** against comparable companies
3. **Build bottom-up model** in spreadsheet for sensitivity analysis
4. **Prepare for questions** on every assumption
5. **Be conservative** - better to beat projections than miss them

---

*Financial Model Template Version: 1.0*
*Last Updated: January 2026*
*Note: All numbers are illustrative examples. Build actual model with real data.*
