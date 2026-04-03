# Asset Management — Lumena OS

## Overview

Every media asset (thumbnails, B-roll, audio, graphics, templates) is tagged, organized, and searchable. No more digging through Google Drive folders or re-creating graphics that already exist.

---

## Asset Types

| Type            | Formats              | Storage           | Examples                              |
|-----------------|----------------------|-------------------|---------------------------------------|
| Thumbnails      | PNG, JPG             | Google Drive      | YouTube thumbnails, podcast covers    |
| B-Roll          | MP4, MOV             | Google Drive      | Lifestyle shots, property walkthroughs|
| Audio Clips     | MP3, WAV             | Google Drive      | Podcast intros, sound bites           |
| Graphics        | PNG, SVG, PSD, Canva | Canva / Drive     | Quote cards, data visuals, carousels  |
| Templates       | Canva, Figma, PSD    | Canva / Drive     | Thumbnail templates, story templates  |
| Documents       | PDF, DOCX            | Google Drive      | One-pagers, guides, lead magnets      |
| Brand Assets    | PNG, SVG, AI         | Google Drive      | Logos, icons, color palettes, fonts   |
| Raw Footage     | MP4, MOV             | External Drive    | Unedited video files                  |
| Transcripts     | TXT, SRT             | Google Drive      | Video/podcast transcripts, captions   |

---

## Folder Structure (Google Drive)

```
Juniper Rose Media/
├── Brand/
│   ├── Logos/
│   ├── Colors-Fonts/
│   ├── Brand-Guidelines/
│   └── Headshots/
├── Thumbnails/
│   ├── YouTube/
│   ├── Podcast/
│   └── Templates/
├── B-Roll/
│   ├── Lifestyle/
│   ├── Real-Estate/
│   ├── Office/
│   └── Events/
├── Graphics/
│   ├── Quote-Cards/
│   ├── Data-Visuals/
│   ├── Carousels/
│   └── Story-Templates/
├── Audio/
│   ├── Intros-Outros/
│   ├── Sound-Bites/
│   └── Music/
├── Documents/
│   ├── Lead-Magnets/
│   ├── One-Pagers/
│   └── Presentations/
├── Transcripts/
│   ├── YouTube/
│   └── Podcast/
└── Archive/
    └── [Year]/
        └── [Quarter]/
```

---

## File Naming Convention

```
[date]_[type]_[topic]_[platform]_[version].[ext]

Examples:
2026-04-03_thumb_first-time-buyer-mistakes_youtube_v1.png
2026-04-03_reel_market-update-q2_instagram_v2.mp4
2026-04-03_carousel_wealth-tips_instagram_v1.canva
2026-04-03_transcript_ep45-investing-basics_podcast.srt
```

### Naming Rules

- **Date:** YYYY-MM-DD format
- **Type:** thumb, reel, broll, graphic, carousel, audio, doc, transcript
- **Topic:** kebab-case, 3-5 words max
- **Platform:** youtube, instagram, tiktok, linkedin, podcast, blog, email
- **Version:** v1, v2, v3 (increment on revisions)
- **No spaces** — use hyphens only
- **Lowercase** everything

---

## Asset Database (Notion)

Track all assets in a Notion database linked to the Content Pipeline.

### Properties

| Property         | Type          | Description                                    |
|------------------|---------------|------------------------------------------------|
| Asset Name       | Title         | Descriptive name                               |
| Asset Type       | Select        | Thumbnail, B-Roll, Graphic, Audio, Template, etc. |
| File Link        | URL           | Google Drive or Canva link                     |
| Content Piece    | Relation      | Links to Content Pipeline DB                   |
| Platform         | Multi-select  | Which platform(s) this asset is for            |
| Category         | Select        | Real Estate, Wealth, Nonprofit, Lifestyle, Brand |
| Tags             | Multi-select  | Searchable tags (see tagging taxonomy below)   |
| Created Date     | Date          | When the asset was created                     |
| Creator          | Person        | Who made it                                    |
| Status           | Select        | Draft, Final, Archived                         |
| Reusable         | Checkbox      | Can this asset be used in future content?      |
| Usage Count      | Number        | How many times this asset has been used        |

### Views

| View Name         | Filter/Group                          | Purpose                        |
|-------------------|---------------------------------------|--------------------------------|
| All Assets        | None                                  | Full library                   |
| By Type           | Grouped by Asset Type                 | Find specific asset types      |
| By Platform       | Grouped by Platform                   | Platform-specific assets       |
| Reusable Library  | Reusable = true, Status = Final       | Stock assets for reuse         |
| Recent            | Created Date = last 30 days           | Newest assets                  |
| Needs Review      | Status = Draft                        | Assets awaiting finalization   |
| By Content Piece  | Grouped by Content Piece relation     | Assets per content piece       |

---

## Tagging Taxonomy

Use consistent tags for searchability.

### Subject Tags
`real-estate` `investing` `wealth` `nonprofit` `community` `personal` `behind-the-scenes` `market-data` `tips` `tutorial` `story` `testimonial` `event` `announcement`

### Visual Tags
`talking-head` `property` `lifestyle` `data-chart` `quote` `text-overlay` `split-screen` `before-after` `aerial` `interior` `exterior` `portrait` `group`

### Mood Tags
`energetic` `calm` `professional` `casual` `inspirational` `educational` `urgent` `celebratory`

### Technical Tags
`vertical` `horizontal` `square` `4k` `1080p` `animated` `static` `template` `editable`

---

## Template Library

Pre-built templates for recurring content formats. Stored in Canva with backup PSD/PNG in Drive.

### Thumbnail Templates

| Template Name            | Use Case                        | Dimensions   |
|--------------------------|---------------------------------|-------------|
| Bold Statement           | Hot take / opinion videos       | 1280x720    |
| Data Highlight           | Market updates, stats           | 1280x720    |
| Before/After             | Transformation stories          | 1280x720    |
| List Format              | "5 Things..." style videos      | 1280x720    |
| Question                 | FAQ / educational videos        | 1280x720    |

### Social Templates

| Template Name            | Use Case                        | Dimensions   |
|--------------------------|---------------------------------|-------------|
| Quote Card               | Pull quotes for IG/LinkedIn     | 1080x1080   |
| Carousel Slide           | Multi-slide educational posts   | 1080x1350   |
| Story Poll               | Engagement stories              | 1080x1920   |
| Stat Highlight           | Data points for social          | 1080x1080   |
| CTA Slide                | End slide for carousels         | 1080x1350   |

### Document Templates

| Template Name            | Use Case                        | Format       |
|--------------------------|---------------------------------|-------------|
| Lead Magnet — Checklist  | Downloadable PDF checklists     | PDF (Canva)  |
| Lead Magnet — Guide      | Multi-page guides               | PDF (Canva)  |
| One-Pager                | Partnership / service overview  | PDF (Canva)  |
| Presentation Deck        | Speaking engagements            | PPTX / Canva |

---

## Asset Workflow

```
Asset Created
    │
    ├── Save to correct Drive folder (follow naming convention)
    ├── Add to Notion Asset DB with tags
    ├── Link to Content Piece (if applicable)
    ├── Set Status = "Draft"
    │
    ├── Review / Approve
    │   └── Set Status = "Final"
    │       └── Mark "Reusable" if applicable
    │
    └── After content is archived (90+ days)
        └── Move to Archive/[Year]/[Quarter]/
            └── Keep Notion entry, update Status = "Archived"
```

---

## Maintenance

- **Monthly:** Review assets tagged "Draft" — finalize or delete
- **Quarterly:** Archive assets older than 90 days that aren't marked reusable
- **Quarterly:** Audit reusable library — remove outdated brand assets
- **Annually:** Purge archive folder for assets older than 2 years (unless evergreen)
