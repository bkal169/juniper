# KPI Definitions — Lumena OS Analytics

## Overview

Every metric tracked in Lumena OS has a clear definition, data source, and target. No vanity metrics — everything ties back to audience growth, engagement, or revenue.

---

## Tier 1: North Star Metrics

These are reviewed weekly and drive strategic decisions.

| Metric                     | Definition                                          | Source              | Target (Monthly)     |
|----------------------------|-----------------------------------------------------|---------------------|----------------------|
| Content Revenue             | Total revenue attributed to content-driven leads    | CRM + UTM tracking  | Growth MoM           |
| Audience Growth Rate        | Net new subscribers/followers across all platforms   | Platform analytics  | 10%+ MoM             |
| Content-to-Lead Rate        | Leads generated / total content pieces published    | CRM + Pipeline DB   | 2+ leads per piece   |
| Publishing Consistency      | Pieces published / pieces planned                   | Pipeline DB         | 90%+                 |

---

## Tier 2: Platform Metrics

Tracked per platform, reviewed weekly.

### YouTube

| Metric             | Definition                              | Target               |
|--------------------|-----------------------------------------|----------------------|
| Views              | Total views per video (28-day window)   | 500+ per video       |
| Watch Time         | Total minutes watched                   | 60%+ avg retention   |
| CTR                | Click-through rate on impressions       | 6%+                  |
| Subscribers Gained | Net new subs per video                  | 10+ per video        |
| Comments           | Total comments per video                | 15+ per video        |

### Podcast

| Metric             | Definition                              | Target               |
|--------------------|-----------------------------------------|----------------------|
| Downloads          | Total downloads per episode (30-day)    | 200+ per episode     |
| Completion Rate    | % of listeners who finish the episode   | 60%+                 |
| Reviews            | New ratings/reviews per month           | 4+ per month         |
| Subscriber Growth  | Net new podcast subscribers             | 50+ per month        |

### Blog / SEO

| Metric             | Definition                              | Target               |
|--------------------|-----------------------------------------|----------------------|
| Organic Traffic    | Unique visitors from search             | 20%+ MoM growth      |
| Avg Time on Page   | Average session duration per post       | 3+ minutes           |
| Keyword Rankings   | Posts ranking on page 1 for target kw   | 2+ new per month     |
| Email Signups      | Blog → newsletter conversions           | 3%+ conversion rate  |

### Social (Instagram / TikTok / LinkedIn / X)

| Metric             | Definition                              | Target               |
|--------------------|-----------------------------------------|----------------------|
| Reach              | Unique accounts reached per post        | Platform-dependent   |
| Engagement Rate    | (Likes + Comments + Shares) / Reach     | 5%+ (IG), 3%+ (LI)  |
| Saves / Bookmarks  | Content saves (high-intent signal)      | 2%+ of reach         |
| Profile Visits     | Visits driven to profile from content   | Track trend          |
| Link Clicks        | Clicks on bio link or story links       | Track trend          |

### Email / Newsletter

| Metric             | Definition                              | Target               |
|--------------------|-----------------------------------------|----------------------|
| Open Rate          | Unique opens / delivered                | 40%+                 |
| Click Rate         | Unique clicks / delivered               | 5%+                  |
| List Growth        | Net new subscribers per month           | 100+ per month       |
| Unsubscribe Rate   | Unsubs / delivered                      | Under 0.5%           |
| Revenue per Send   | Revenue attributed to email sends       | Track trend          |

---

## Tier 3: Content Quality Metrics

Tracked per content piece in the Pipeline DB.

| Metric              | Definition                                      | Tracked In         |
|---------------------|--------------------------------------------------|--------------------|
| 7-Day Score         | Weighted composite (views, engagement, CTR, conversions) | Pipeline DB formula |
| 30-Day Score        | Extended composite with revenue attribution       | Pipeline DB formula |
| Performance Tier    | S/A/B/C/D rating based on 30-Day Score            | Pipeline DB formula |
| Repurpose Count     | Number of derivative pieces created from original | Pipeline DB        |
| Evergreen Flag      | Content still driving traffic after 90 days       | Manual tag         |

---

## Reporting Cadence

| Report              | Frequency    | Contents                                          |
|---------------------|-------------|---------------------------------------------------|
| Daily Brief         | Daily 7:30AM| Yesterday's publishes, today's schedule, alerts   |
| Weekly Scorecard    | Monday AM   | All Tier 1 + Tier 2 metrics, week-over-week       |
| Monthly Review      | 1st of month| Full metrics review, top/bottom performers, trends |
| Quarterly Strategy  | Quarter start| Performance vs goals, next quarter planning        |

---

## Performance Tier Benchmarks

| Tier | 30-Day Score | Action                                           |
|------|-------------|--------------------------------------------------|
| S    | 500+        | Repurpose aggressively, model future content after |
| A    | 300–499     | Repurpose, create follow-up content               |
| B    | 150–299     | Standard — on track                               |
| C    | 50–149      | Review what underperformed, test adjustments       |
| D    | Under 50    | Audit: wrong topic, bad hook, wrong platform?      |

---

## Dashboard Layout (Notion)

### Weekly Scorecard View
```
┌─────────────────────────────────────────────────┐
│  LUMENA OS — Weekly Scorecard                    │
├──────────────┬──────────────┬───────────────────┤
│ Published    │ Leads Gen'd  │ Revenue Attributed│
│   12/14      │     18       │    $4,200         │
├──────────────┴──────────────┴───────────────────┤
│  Platform Breakdown                              │
│  YT: 3 videos | 2,400 views | 8.2% CTR          │
│  Pod: 1 ep | 340 downloads                       │
│  Blog: 2 posts | 890 organic visits              │
│  Social: 4 posts | 12,000 reach | 6.1% eng       │
│  Email: 1 send | 42% open | 6.8% click           │
├─────────────────────────────────────────────────┤
│  Top Performer: "5 Mistakes First-Time Buyers    │
│  Make" — S tier, 1,200 views, 14 leads           │
└─────────────────────────────────────────────────┘
```
