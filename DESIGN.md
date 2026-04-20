\# DESIGN.md



\## Purpose



This document defines the design principles and implementation guidance for Rakuten-branded user interfaces, content, and generated artifacts.



The goal is to preserve \*\*brand unity and consistency\*\* while allowing enough flexibility to express the \*\*diversity of Rakuten services and messages\*\*. The Rakuten type system was developed to support websites, apps, and other content across the Rakuten ecosystem. :contentReference\[oaicite:1]{index=1}



\---



\## Core Design Principles



\### 1. Balance unity and diversity

Rakuten design should feel like one family across products, while still allowing different services or messages to express distinct personalities. Use a shared visual foundation first, then introduce variation only when it improves communication. :contentReference\[oaicite:2]{index=2}



\### 2. Prioritize clarity and function

Typography and layout should support communication before decoration. Choose solutions that improve readability, scanability, and comprehension, especially in product UI and content-heavy screens. Rakuten’s type design emphasizes both expression and functionality. :contentReference\[oaicite:3]{index=3}



\### 3. Use brand expression deliberately

Brand character may be expressed through font style, weight, spacing, and composition, but never at the cost of usability. Stronger stylistic choices should be reserved for emphasis, campaigns, and storytelling moments. :contentReference\[oaicite:4]{index=4}



\### 4. Design for multilingual scale

Interfaces and content should anticipate multilingual use. The Rakuten font family extends coverage across nearly all European languages and includes expanded Latin and Cyrillic support, so layouts should be prepared for international text expansion and varied glyph shapes. :contentReference\[oaicite:5]{index=5}



\---



\## Rakuten Typeface System



Rakuten’s type system includes \*\*four primary styles\*\* designed from the form of the Rakuten logo:



\- \*\*Rakuten Sans\*\*

\- \*\*Rakuten Serif\*\*

\- \*\*Rakuten Rounded\*\*

\- \*\*Rakuten Condensed\*\*



These styles were created as a family with distinct personalities so designers can choose the one that best fits the message while maintaining consistency with Rakuten brand assets. :contentReference\[oaicite:6]{index=6}



\### Approved usage mindset

\- Prefer \*\*Rakuten Sans\*\* as the default general-purpose typeface.

\- Use \*\*Rakuten Serif\*\* when a more editorial, refined, or expressive tone is needed.

\- Use \*\*Rakuten Rounded\*\* when a friendlier, softer, or more approachable tone is appropriate.

\- Use \*\*Rakuten Condensed\*\* only where space efficiency or stronger vertical rhythm is needed, and verify readability carefully.  

These recommendations are implementation guidance based on the published style family structure; they are not direct quotations of an official priority order. The source confirms the existence of these four styles, not a mandatory default hierarchy. :contentReference\[oaicite:7]{index=7}



\---



\## Typography Characteristics



\### Rakuten Sans

Rakuten Sans is described as a geometric sans serif with:

\- tapered spurs

\- open counters

\- slightly flared terminals on curved strokes



These features aim to preserve legibility at smaller sizes while keeping a sharp and distinctive personality. :contentReference\[oaicite:8]{index=8}



\### Italics

Rakuten Sans upright styles are accompanied by \*\*true italic\*\* matching fonts with cursive construction. Italics should therefore be used for meaningful emphasis rather than artificial slanting. Do not simulate italics if the real italic font is available. :contentReference\[oaicite:9]{index=9}



\### Weight range

The published family shows the following static weights:

\- Light

\- Regular

\- Semibold

\- Bold

\- Black :contentReference\[oaicite:10]{index=10}



Use weight contrast intentionally:

\- \*\*Regular\*\* for most body text

\- \*\*Semibold\*\* for UI emphasis and section headers

\- \*\*Bold\*\* for strong emphasis

\- \*\*Black\*\* sparingly, mainly for impact or campaign moments



Avoid overusing heavy weights in dense UI or long-form reading contexts.



\---



\## Variable Font Guidance



For each font style, Rakuten provides a \*\*Variable Font\*\* implementation. Variable fonts make all weights of a style accessible through a single file, reducing file size and allowing continuous weight selection on the weight axis. The published example shows a weight axis from \*\*300 to 900\*\* for the demonstration. :contentReference\[oaicite:11]{index=11}



\### Practical rules

\- Prefer variable fonts in modern digital environments when supported.

\- Use static fonts only when technical constraints require them.

\- Use intermediate variable weights only when they solve a specific visual problem; otherwise stay close to standard weights for consistency.

\- Do not introduce excessive micro-variation across components.



\### Performance guidance

The Rakuten page explicitly notes that variable fonts can produce \*\*smaller file sizes for better performance\*\* by consolidating multiple weights into a single file. When optimizing frontend delivery, prefer fewer font files and fewer active styles. :contentReference\[oaicite:12]{index=12}



\---



\## Language and Character Support



The Rakuten Sans and Serif families are presented as covering \*\*almost all European languages\*\* and including a \*\*complete all-European Latin and Cyrillic glyph set\*\*. The published character-set description also references:

\- proportional figures

\- tabular figures

\- superiors and inferiors

\- punctuation

\- capital punctuation

\- symbols

\- extended language support

\- standard ligatures

\- stylistic alternates

\- base Cyrillic

\- extended Cyrillic

\- Cyrillic symbols/support :contentReference\[oaicite:13]{index=13}



\### Internationalization rules

\- Do not assume English-only layouts.

\- Test with longer localized strings.

\- Confirm glyph rendering for Cyrillic and extended Latin content before release.

\- Use tabular figures where numeric alignment matters, such as tables, dashboards, timers, pricing matrices, and financial summaries.

\- Prefer proportional figures in marketing or editorial contexts unless alignment is critical.



\---



\## Hierarchy and Composition



\### General hierarchy

\- Build hierarchy first with \*\*size\*\*, then \*\*weight\*\*, then \*\*spacing\*\*.

\- Avoid relying on color alone to indicate importance.

\- Keep heading systems simple and repeatable.

\- Preserve strong contrast between title, subtitle, body, and caption.



\### Density

\- Give text enough room to breathe.

\- Use Condensed styles only when necessary.

\- Preserve readability in narrow containers and mobile layouts.



\### Emphasis

\- Prefer one strong emphasis method at a time:

&#x20; - weight

&#x20; - italic

&#x20; - size

&#x20; - spacing  

&#x20; Avoid stacking all of them unless the design intentionally calls for a display moment.



\---



\## Recommended Default Choices for Product UI



These are implementation defaults intended for code generation and design systems. They are not stated verbatim on the source page, but they align with the published characteristics of the Rakuten font family. :contentReference\[oaicite:14]{index=14}



\### Default font selection

\- Primary UI font: \*\*Rakuten Sans\*\*

\- Secondary editorial/display option: \*\*Rakuten Serif\*\*

\- Friendly/supportive moments: \*\*Rakuten Rounded\*\*

\- Space-constrained utility use: \*\*Rakuten Condensed\*\*



\### Suggested weight usage

\- Body: `Regular`

\- Label / strong UI text: `Semibold`

\- Section heading: `Semibold` or `Bold`

\- Display headline: `Bold` or `Black`

\- Fine print / metadata: `Regular` or `Light` only if contrast remains accessible



\### Italic usage

\- Use true italic only for intentional emphasis or editorial nuance.

\- Do not overuse italic in forms, tables, navigation, or dense dashboards.



\---



\## Accessibility and Readability Rules



The source explicitly highlights legibility through open counters and functional construction. Accessibility should therefore be treated as part of brand fidelity, not as a separate concern. :contentReference\[oaicite:15]{index=15}



\### Mandatory rules

\- Maintain sufficient text contrast.

\- Do not use very light weights for small interactive text.

\- Avoid condensed text for long paragraphs.

\- Avoid decorative typography in critical workflows.

\- Ensure headings and controls remain readable at small sizes.

\- Validate readability across desktop and mobile breakpoints.



\### Numeric and data display

\- Prefer tabular figures for aligned numeric columns.

\- Verify decimal and currency alignment in financial interfaces.

\- Use consistent weight and spacing for metric cards and dashboards.



\---



\## Brand Tone Through Typeface Selection



When generating or reviewing designs, choose a type style that matches the communication goal:



\- \*\*Sans\*\*: default, modern, practical, trustworthy

\- \*\*Serif\*\*: premium, editorial, thoughtful, expressive

\- \*\*Rounded\*\*: warm, human, accessible, friendly

\- \*\*Condensed\*\*: efficient, compact, assertive



These tone mappings are interpretive guidance derived from the published existence of distinct styles with distinct personalities. They should be used as internal implementation heuristics. :contentReference\[oaicite:16]{index=16}



\---



\## Do / Don’t



\### Do

\- Use the Rakuten font family consistently across websites, apps, and content.

\- Prefer variable fonts when supported.

\- Choose a style that matches the message while staying within the Rakuten family.

\- Preserve readability at small sizes.

\- Support multilingual content from the start.

\- Keep file delivery efficient by minimizing unnecessary font variants. :contentReference\[oaicite:17]{index=17}



\### Don’t

\- Mix unrelated typefaces when a Rakuten family style can solve the need.

\- Fake italic or bold when proper font files exist.

\- Use heavy display styling in transactional or high-density UI.

\- Assume Latin-only content.

\- Use Condensed as the default body typeface.

\- Sacrifice clarity for novelty.



\---



\## Guidance for AI Coding Agents



When generating UI, documents, HTML, CSS, React components, app screens, or design specs for Rakuten-branded work, follow these rules:



1\. Use the \*\*Rakuten type family\*\* whenever available.

2\. Default to \*\*Rakuten Sans\*\* for UI and product surfaces.

3\. Use \*\*Semibold\*\* for emphasis before escalating to Bold or Black.

4\. Prefer \*\*variable fonts\*\* over loading many static files when browser/platform support allows.

5\. Keep typography readable, restrained, and scalable.

6\. Anticipate multilingual layouts, including expanded Latin and Cyrillic text.

7\. Use typography to clarify structure and meaning, not as decoration alone.

8\. When in doubt, choose the option that is more consistent, more legible, and more performant. :contentReference\[oaicite:18]{index=18}



\---



\## Example Design Intent for Generated Output



\### For product UI

Use Rakuten Sans, moderate weight contrast, clear hierarchy, compact but readable spacing, and restrained stylistic expression.



\### For campaign or branded storytelling

Allow stronger font personality, including Serif or Rounded where appropriate, but preserve clarity and consistency with the Rakuten system.



\### For dashboards and data-heavy views

Use Rakuten Sans, tabular figures where possible, consistent alignment, and minimal decorative variation.



\---



\## Source Note



This document is based on the Rakuten Design page for the variable Latin/Cyrillic font system, which describes:

\- the purpose of the Rakuten font family

\- the four type styles

\- the existence and benefits of variable fonts

\- language coverage

\- Rakuten Sans design characteristics

\- available character sets and weights

\- collaboration with Dalton Maag :contentReference\[oaicite:19]{index=19}



Where this file provides operational recommendations for engineering or AI generation, those parts are implementation guidance derived from the published design intent, not direct quotations from Rakuten.

