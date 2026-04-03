# Content Automations — Lumena OS

## Overview

Zapier/Make blueprints for automating the Lumena OS content pipeline. These automations eliminate manual handoffs between pipeline stages and ensure nothing falls through the cracks.

---

## Automation 1: Content Pipeline Stage Notifications

**Trigger:** Content Pipeline DB → Stage property changes
**Platform:** Zapier or Make

### Flows

| Stage Change         | Action                                                    |
|----------------------|-----------------------------------------------------------|
| → Research           | Notify creator via Slack/email: "Research phase started"  |
| → Draft              | Start draft timer, notify creator                         |
| → Review             | Notify editor/Alan: "New content ready for review"        |
| → Approved           | Notify ops: "Content approved — schedule for publish"     |
| → Scheduled          | Confirm schedule, create calendar event                   |
| → Published          | Start 7-day analytics timer, log to Automation Log        |
| → Analyzing          | Capture metrics snapshot, calculate 7-Day Score           |
| → Archived           | Final metrics capture, tag for repurpose if S/A tier      |

### Zapier Setup

```
Trigger: Notion — Database Item Updated (Content Pipeline DB)
Filter: Stage property has changed
Action 1: Slack — Send Channel Message
  Channel: #content-ops
  Message: "[Content Title] moved to [New Stage] by [Person]"
Action 2: Notion — Update Database Item (Automation Log)
  Log entry: timestamp, content title, stage change, actor
```

---

## Automation 2: Auto-Schedule Published Content Analytics

**Trigger:** Content Pipeline DB → Stage = "Published"
**Platform:** Zapier (with Delay steps)

```
Trigger: Notion — Database Item Updated
Filter: Stage = "Published"

Action 1 (Immediate):
  - Log "Published" event to Automation Log
  - Create Google Calendar reminder: "7-day review for [Title]"

Action 2 (Delay 7 days):
  - Pull platform metrics (YouTube API / Instagram API / etc.)
  - Update Content Pipeline DB: Views, Engagement Rate, CTR
  - Calculate 7-Day Score
  - Move Stage to "Analyzing"

Action 3 (Delay 30 days from publish):
  - Pull updated platform metrics
  - Update 30-Day Score and Performance Tier
  - If Tier = S or A: tag for repurpose, notify content team
  - Move Stage to "Archived"
```

---

## Automation 3: Editorial Calendar Sync

**Trigger:** Content Pipeline DB → Stage = "Scheduled"
**Platform:** Zapier

```
Trigger: Notion — Database Item Updated
Filter: Stage = "Scheduled" AND Publish Date is set

Action 1: Google Calendar — Create Event
  Title: "📢 PUBLISH: [Content Title]"
  Date/Time: [Publish Date from Notion]
  Description: "Platform: [Primary Platform] | Type: [Content Type]"
  Calendar: Juniper Rose Content Calendar

Action 2: Notion — Update Database Item (Content Pipeline)
  Set "Calendar Synced" checkbox to true

Action 3 (Day of publish, 1 hour before):
  Slack notification: "Reminder: [Title] publishes in 1 hour on [Platform]"
```

---

## Automation 4: Repurpose Task Generator

**Trigger:** Content Pipeline DB → Stage = "Published" AND Content Type = YouTube/Podcast/Blog
**Platform:** Zapier or Make

```
Trigger: Notion — Database Item Updated
Filter: Stage = "Published"

Action: Create derivative tasks based on content type

IF Content Type = "YouTube":
  Create 7 tasks in Content Pipeline DB:
  - "[Title] — Reel Clip 1" (Type: Reel, Due: today)
  - "[Title] — Reel Clip 2" (Type: TikTok, Due: today)
  - "[Title] — YouTube Short" (Type: YouTube Short, Due: +1 day)
  - "[Title] — LinkedIn Quote" (Type: LinkedIn, Due: +1 day)
  - "[Title] — X Thread" (Type: Thread, Due: +2 days)
  - "[Title] — Blog Adaptation" (Type: Blog, Due: +3 days)
  - "[Title] — Email Mention" (Type: Email, Due: next Thursday)
  Each task:
  - Stage: "Idea"
  - Priority: P2
  - Relation: linked to original content piece
  - Category: same as original

IF Content Type = "Podcast":
  Create 5 derivative tasks (per distribution matrix)

IF Content Type = "Blog":
  Create 4 derivative tasks (per distribution matrix)
```

---

## Automation 5: Daily Content Brief (7:30 AM ET)

**Trigger:** Schedule — Daily at 7:30 AM ET
**Platform:** Zapier

```
Trigger: Schedule — Every Day at 7:30 AM ET

Step 1: Notion — Query Content Pipeline DB
  Filter: Publish Date = today OR Stage = "Review" OR Due Date = today

Step 2: Notion — Query Content Pipeline DB
  Filter: Stage = "Analyzing" AND Published in last 7 days
  (For yesterday's metrics)

Step 3: Google Calendar — Get Events
  Filter: Today's events

Step 4: OpenAI — Generate Brief
  Prompt: Daily Operations Brief template (from prompt-library.md)
  Inputs: Query results from Steps 1–3

Step 5: Notion — Create Database Item (Daily Briefs DB)
  Title: "Daily Brief — [Date]"
  Content: Generated brief

Step 6: Email — Send
  To: alan@juniperrose.com
  Subject: "☀️ Daily Brief — [Date]"
  Body: Generated brief

Step 7: Slack — Send Message
  Channel: #daily-brief
  Message: Generated brief
```

---

## Automation 6: New Idea Intake

**Trigger:** Content Pipeline DB → New item created with Stage = "Idea"
**Platform:** Zapier

```
Trigger: Notion — New Database Item (Content Pipeline DB)
Filter: Stage = "Idea"

Action 1: Auto-set Priority to P4 (backlog)
Action 2: Auto-set Creator to person who created it
Action 3: Slack notification to #content-ideas
  Message: "💡 New content idea: [Title] | Type: [Content Type] | Category: [Category]"
Action 4: Log to Automation Log
```

---

## Automation 7: YouTube Upload → Notion Sync

**Trigger:** YouTube — New Video Published
**Platform:** Zapier

```
Trigger: YouTube — New Video (connected channel)

Action 1: Notion — Find Database Item (Content Pipeline DB)
  Search by: Title contains [Video Title]

Action 2 (If found): Update existing item
  - Stage → "Published"
  - Publish Date → [YouTube publish date]
  - Tracking Link → [YouTube URL with UTM]

Action 3 (If not found): Create new item
  - Title: [Video Title]
  - Content Type: "YouTube"
  - Stage: "Published"
  - Publish Date: [YouTube publish date]
  - Primary Platform: "YouTube"

Action 4: Log to Automation Log
```

---

## Automation 8: Weekly Performance Digest

**Trigger:** Schedule — Every Monday at 8:00 AM ET
**Platform:** Zapier

```
Trigger: Schedule — Every Monday at 8:00 AM ET

Step 1: Notion — Query Content Pipeline DB
  Filter: Published in last 7 days

Step 2: Notion — Query Content Pipeline DB
  Filter: Performance Tier = "S" or "A" (last 30 days)

Step 3: OpenAI — Generate Digest
  Prompt: "Summarize this week's content performance for Juniper Rose.
  Published this week: [Step 1 results]
  Top performers (last 30 days): [Step 2 results]
  Include: total pieces published, total views, top performer,
  worst performer, trend vs last week, recommended actions."

Step 4: Email — Send
  To: alan@juniperrose.com
  Subject: "📊 Weekly Content Scorecard — [Week of Date]"

Step 5: Notion — Create item in Daily Briefs DB
  Title: "Weekly Scorecard — [Date]"
```

---

## Automation Log Schema

Every automation run gets logged to the Automation Log DB:

| Property       | Type     | Description                           |
|----------------|----------|---------------------------------------|
| Timestamp      | Date     | When the automation ran                |
| Automation     | Select   | Which automation triggered             |
| Status         | Select   | Success / Partial / Error              |
| Content Piece  | Relation | Related content piece (if applicable)  |
| Details        | Text     | What happened, what changed            |
| Error Message  | Text     | Error details (if Status = Error)      |

---

## Setup Order

Wire automations in this sequence:

1. **New Idea Intake** (simplest, test your Notion connection)
2. **Stage Notifications** (core pipeline visibility)
3. **Editorial Calendar Sync** (scheduling workflow)
4. **Daily Content Brief** (daily operations)
5. **Repurpose Task Generator** (content multiplication)
6. **YouTube Upload Sync** (platform integration)
7. **Auto-Schedule Analytics** (performance tracking)
8. **Weekly Performance Digest** (reporting)
