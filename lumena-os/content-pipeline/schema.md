# Content Pipeline Schema — Lumena OS

## Overview

Every piece of content moves through a defined pipeline from ideation to performance review. This replaces ad-hoc content creation with a trackable, repeatable system.

---

## Pipeline Stages

```
IDEA → RESEARCH → DRAFT → REVIEW → APPROVED → SCHEDULED → PUBLISHED → ANALYZING → ARCHIVED
```

| Stage       | Owner        | Exit Criteria                                        |
|-------------|-------------|------------------------------------------------------|
| Idea        | Anyone       | Topic defined, target audience selected, format chosen |
| Research    | Creator      | Outline complete, sources gathered, keyword identified |
| Draft       | Creator      | Full draft written, media assets identified            |
| Review      | Editor/Alan  | Brand voice check passed, facts verified, CTA present  |
| Approved    | Editor/Alan  | Final sign-off, no open comments                       |
| Scheduled   | Ops          | Platform selected, date/time set, assets uploaded       |
| Published   | Automated    | Live on platform, tracking links active                 |
| Analyzing   | Ops          | 7-day and 30-day metrics captured                      |
| Archived    | Automated    | Performance data logged, content tagged for repurpose   |

---

## Content Database Properties

### Core Fields

| Property          | Type          | Description                                    |
|-------------------|---------------|------------------------------------------------|
| Title             | Title         | Content piece name                             |
| Stage             | Select        | Current pipeline stage (see above)             |
| Content Type      | Select        | YouTube, Podcast, Blog, Reel, TikTok, Email, LinkedIn, Thread |
| Category          | Select        | Real Estate, Wealth, Nonprofit, Lifestyle, Behind the Scenes |
| Target Audience   | Multi-select  | Segment tags from voice-config                 |
| Creator           | Person        | Assigned content creator                       |
| Due Date          | Date          | Target completion date                         |
| Publish Date      | Date          | Scheduled or actual publish date               |
| Priority          | Select        | P1 (urgent), P2 (this week), P3 (this month), P4 (backlog) |

### Production Fields

| Property          | Type          | Description                                    |
|-------------------|---------------|------------------------------------------------|
| Outline           | URL/Text      | Link to outline doc or inline outline          |
| Draft             | URL           | Link to draft (Google Doc, Notion page)        |
| Script            | Rich Text     | Final script or copy                           |
| Media Assets      | Files/URLs    | Thumbnails, B-roll, audio, graphics            |
| SEO Keyword       | Text          | Primary keyword target                         |
| Hook              | Text          | Opening hook (first 8 seconds / first line)    |
| CTA               | Text          | Call-to-action for this piece                  |

### Distribution Fields

| Property          | Type          | Description                                    |
|-------------------|---------------|------------------------------------------------|
| Primary Platform  | Select        | Where this publishes first                     |
| Repurpose To      | Multi-select  | Platforms to repurpose content for              |
| Tracking Link     | URL           | UTM-tagged link for attribution                |
| Hashtags          | Text          | Platform-specific hashtag sets                 |

### Analytics Fields

| Property          | Type          | Description                                    |
|-------------------|---------------|------------------------------------------------|
| Views             | Number        | Total views/impressions                        |
| Engagement Rate   | Number        | Likes + comments + shares / views              |
| Click-through     | Number        | CTA clicks or link clicks                      |
| Conversions       | Number        | Leads, signups, or sales attributed            |
| Revenue           | Number        | Dollar value attributed to this content        |
| 7-Day Score       | Formula       | Weighted performance score at 7 days           |
| 30-Day Score      | Formula       | Weighted performance score at 30 days          |
| Performance Tier  | Formula       | S / A / B / C / D based on 30-day score        |

---

## Notion Formulas

### 7-Day Score
```
(prop("Views") * 0.2) + (prop("Engagement Rate") * 100 * 0.3) + (prop("Click-through") * 0.2) + (prop("Conversions") * 50 * 0.3)
```

### 30-Day Score
```
(prop("Views") * 0.15) + (prop("Engagement Rate") * 100 * 0.25) + (prop("Click-through") * 0.15) + (prop("Conversions") * 50 * 0.25) + (prop("Revenue") * 0.2)
```

### Performance Tier
```
if(prop("30-Day Score") >= 500, "S",
if(prop("30-Day Score") >= 300, "A",
if(prop("30-Day Score") >= 150, "B",
if(prop("30-Day Score") >= 50, "C", "D"))))
```

---

## Database Views

| View Name              | Filter                              | Sort              | Purpose                          |
|------------------------|-------------------------------------|-------------------|----------------------------------|
| Active Pipeline        | Stage ≠ Archived                    | Stage → Due Date  | Daily production view            |
| My Queue               | Creator = me, Stage ≠ Archived      | Priority → Due    | Personal task view               |
| Ready for Review       | Stage = Review                      | Due Date          | Editor review queue              |
| Publishing Queue       | Stage = Approved OR Scheduled       | Publish Date      | What's going out and when        |
| This Week              | Due Date = this week                | Priority          | Weekly sprint view               |
| Performance Board      | Stage = Analyzing                   | 7-Day Score desc  | What's performing                |
| Top Performers         | Performance Tier = S or A           | 30-Day Score desc | Best content for repurposing     |
| Content Library        | Stage = Archived                    | Category → Date   | Searchable back-catalog          |
| By Platform            | Group by Primary Platform           | Publish Date      | Platform-specific view           |

---

## Automation Triggers

| Trigger                              | Action                                              |
|--------------------------------------|------------------------------------------------------|
| Stage → Approved                     | Notify ops to schedule, create distribution tasks     |
| Stage → Published                    | Start 7-day analytics timer, create tracking entry    |
| 7 days after Published               | Capture 7-day metrics, calculate 7-Day Score          |
| 30 days after Published              | Capture 30-day metrics, calculate tier, move to Archived |
| Performance Tier = S or A            | Flag for repurpose, add to "Top Performers" view      |
| New Idea created                     | Auto-assign priority P4, notify content team          |
