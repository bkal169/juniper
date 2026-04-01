# Empire OS — Juniper Rose Legacy System

**One hub for Real Estate, Wealth, Nonprofit, Media & Legacy.**

Operate listings, pipelines, content, funding, recruiting, grants, daily briefs, and SOP checklists from a single cockpit — with baked-in automations and AI prompts.

## What's Inside

- **Command Center Dashboard** — Today's Focus, Weekly Checklist, KPI tiles, Daily Briefs, Automation Log
- **CRM & Deals Pipeline** — Relations, stages, rollups, curated "Hot Expireds" & "FSBO 0–14d" views
- **Exhaustive Listing Checklist** — Spawns on "Active Listing" (Pre-Listing → Post-Closing)
- **Content Planner** — YouTube/Podcast/Blog cadence; scripts & outlines via AI prompt
- **Finance Pipelines** — Primerica (recruits/licensing/production), DAC (deals), MLO (loans)
- **Heart of Juniper** — Donors, Grants, Students, Mentors; proposal & thank-you templates
- **Daily Briefs** — Auto-generated 7:30 AM status drop (calendar, tasks, hot leads)
- **Automation Log** — Every integration run (new/updated/duplicates/errors)
- **AI Prompts** — Script generator, Pre-Call Brief, Daily Brief (OpenAI-ready)
- **Zapier/Make Blueprints** — CINC/REDX/Qazzoo → Notion; Calendly → Zoom → Notion; Daily Brief

## Integrations

Notion · Google Drive/Calendar · Calendly · Zoom · CINC · REDX · Qazzoo · Zapier/Make · OpenAI

## Quick Start

1. **Download** the [ZIP template](https://drive.google.com/uc?export=download&id=1i2HYaDl4PYHi6UN_g9f357Bx58Iplg68)
2. **Import** CSVs into Notion (`/databases` folder)
3. **Add Relations/Rollups** per `/schemas/Notion_Property_Schema.txt`
4. **Set Up Templates** from `/templates` into each DB
5. **Build Command Center** page with linked views
6. **Wire Automations** via Zapier or Make using provided blueprints

## Core Automations

| Trigger | Action |
|---------|--------|
| CINC new lead | → Notion CRM → AI call/SMS/email scripts (Day 1–7) |
| REDX email/CSV | → Notion CRM → AI scripts |
| Qazzoo email | → Notion CRM → AI scripts |
| Calendly booking | → Zoom link → Notion Pre-Call Brief |
| Zoom recording done | → AI summary → Tasks |
| Daily (7:30 AM ET) | → Daily Brief → Notion + Email |

## Security

- No credentials stored in shared Notion pages
- De-dupe rules: email → phone → name+ZIP
- DNC checkbox exclusion from call queues
- Automation Log for audit trails

## License

MIT — You are responsible for your data and compliance (DNC, privacy, etc.).

## Credits

Designed by **Alan Augustin** with **Juniper** (AI Operating Partner).
