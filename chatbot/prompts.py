"""Prompt builders for the DrJhaGPT Pro studio.

One function per tool. Each returns a single user-message string; the shared
BASE_SYSTEM below carries voice, formatting and technical-accuracy rules so every
generator produces a document with the same shape and house style.

House style, in short: Markdown only, one '# Title', '## ' sections, fenced code
with a language tag, plain hyphens (never em dashes), no emoji, and an explicit
"[verify]" marker rather than an invented command flag.
"""

BASE_SYSTEM = (
    "You are DrJhaGPT Pro, the authoring assistant of Dr. Pranay Jha - a VMware, "
    "cloud and AI-infrastructure architect who trains engineers and consults for "
    "enterprises. You write the material he teaches from: course outlines, session "
    "plans, lab guides, demo runbooks, assessments, scripts, cheat sheets, runbooks "
    "and handouts.\n\n"

    "AUDIENCE. Working engineers and architects. Write to a professional peer, not "
    "to a beginner being talked down to. Assume general IT literacy; explain only "
    "what is specific to the topic and the stated level.\n\n"

    "TECHNICAL ACCURACY - this matters more than fluency:\n"
    "- Never invent a command, flag, API field, port, path, default value, sizing "
    "number or product capability. If you are not certain something exists in the "
    "stated product version, write it and append ' [verify]' on the same line.\n"
    "- Respect the product and version you are given. Do not describe behaviour "
    "from a different major version as though it were current, and say plainly when "
    "something changed between versions.\n"
    "- Prefer the vendor's current terminology; if a term was recently renamed, give "
    "the new name and the old one once, in brackets.\n"
    "- Give real, runnable commands with realistic placeholder values "
    "(<vcenter-fqdn>, <cluster-name>). Never fake sample output; if you show output, "
    "keep it short and label it as illustrative.\n"
    "- Where a step is destructive or has blast radius, say so before the step.\n\n"

    "VOICE. Direct, practical, senior. Short sentences. Lead with the point. Explain "
    "the 'why' before the 'how' and call out the mistake engineers actually make. No "
    "marketing language, no filler, no 'in today's fast-paced world' openers.\n\n"

    "FORMATTING - follow exactly:\n"
    "- Markdown only. Start with a single '# Title' line.\n"
    "- Use '## ' for sections and '### ' for sub-sections. Never bold a line as a "
    "substitute for a heading.\n"
    "- Every list item on its own line, starting with '- ' or '1. '.\n"
    "- Use tables where a table genuinely helps (comparisons, port lists, sizing, "
    "schedules). Keep them under six columns.\n"
    "- Put every command, snippet, config and output in a fenced code block with a "
    "language tag: ```powershell, ```bash, ```python, ```yaml, ```hcl, ```json, "
    "```sql, ```text.\n"
    "- Plain hyphens for dashes. No emoji. No decorative separators.\n"
    "- Do not add a closing 'I hope this helps' paragraph, and do not describe what "
    "you just produced. Output the document only."
)


def _clean(v, fallback=""):
    v = (v or "").strip()
    return v if v else fallback


def _ctx(area, version, level, audience=""):
    """The shared 'what are we teaching, to whom' preamble every tool sends."""
    bits = [f"Technology area: {_clean(area, 'general infrastructure')}."]
    if _clean(version):
        bits.append(f"Product / version: {version.strip()}. Everything must be "
                    "correct for this exact version; flag anything version-specific.")
    if _clean(level):
        bits.append(f"Audience depth: {level.strip()}.")
    if _clean(audience):
        bits.append(f"Audience role: {audience.strip()}.")
    return " ".join(bits)


def _grounding(context):
    """Attach retrieved passages from drpranayjha.com / an uploaded PDF."""
    if not _clean(context):
        return ""
    return (
        "\n\nGROUNDING. The passages below come from Dr Jha's own published work "
        "and/or a document he uploaded. Prefer them over your own recollection "
        "wherever they overlap, mirror their terminology and positions, and stay "
        "consistent with them. Do not quote them at length and do not mention that "
        "you were given them.\n\n"
        "-----\n" + context.strip()[:6000] + "\n-----"
    )


# =============================================================================
#  Plan & Teach
# =============================================================================
def course_outline(area, version, level, audience, length, mode, goals, context=""):
    return (
        f"Design a complete training course outline.\n\n{_ctx(area, version, level, audience)} "
        f"Total duration: {_clean(length, '2 days')}. Delivery: {_clean(mode, 'instructor-led')}.\n"
        f"Business goal / what learners must be able to do afterwards: "
        f"{_clean(goals, 'become productive with the technology in their day job')}.\n\n"
        "Produce, in this order:\n"
        "1. '# ' the course title, then a two-line positioning statement.\n"
        "2. '## Who this is for' - roles, and the prerequisites they must already "
        "have (be specific: 'comfortable with vSphere HA/DRS', not 'basic knowledge').\n"
        "3. '## Learning outcomes' - 5 to 7 outcomes, each an observable action "
        "starting with a verb (Configure, Troubleshoot, Size, Design).\n"
        "4. '## Course at a glance' - a table of Day / Module / Focus / Duration "
        "covering the whole duration.\n"
        "5. '## Modules in detail' - a '### ' per module with: what it covers, the "
        "hands-on lab or demo attached to it, and the one concept learners most "
        "often get wrong.\n"
        "6. '## Lab environment' - what must exist before day one.\n"
        "7. '## Assessment & follow-up' - how understanding is checked, and what to "
        "study next.\n"
        "Balance the time realistically: no more than 60% lecture, and every module "
        "over 45 minutes gets a hands-on element."
        + _grounding(context)
    )


def session_plan(area, version, level, audience, duration, topic, mode, context=""):
    return (
        f"Write a minute-by-minute plan for ONE training session.\n\n"
        f"{_ctx(area, version, level, audience)} Session length: "
        f"{_clean(duration, '1 hour')}. Delivery: {_clean(mode, 'instructor-led')}.\n"
        f"Topic to cover: {_clean(topic, area)}.\n\n"
        "Produce:\n"
        "1. '# ' session title, then one line on what the learner walks away able to do.\n"
        "2. '## Run sheet' - a table with columns Time | Segment | What I do | "
        "What they do. The times must add up to the session length exactly and "
        "include a hook in the first 5 minutes and a recap at the end.\n"
        "3. '## Talking track' - the actual teaching narrative, section by section, "
        "as short paragraphs I can speak from. Include the analogy I should use.\n"
        "4. '## Demo checkpoints' - each demo, what to show, and the single sentence "
        "to say while it loads.\n"
        "5. '## Questions to ask the room' - 4 questions, with the answer I am "
        "listening for.\n"
        "6. '## Likely questions & how to answer' - 4 questions learners actually "
        "ask on this topic, each with a crisp answer.\n"
        "7. '## Common misconceptions' - what to correct explicitly.\n"
        "8. '## If short on time' - what to cut, in order."
        + _grounding(context)
    )


def slide_outline(area, version, level, audience, topic, count, duration, context=""):
    return (
        f"Write a slide-by-slide deck outline I can paste into PowerPoint.\n\n"
        f"{_ctx(area, version, level, audience)} Topic: {_clean(topic, area)}. "
        f"Target: about {_clean(count, '15')} slides for a "
        f"{_clean(duration, '45 minute')} talk.\n\n"
        "Format every slide as a '### ' heading of the form "
        "'### Slide N - <slide title>' followed by:\n"
        "- 'On slide:' 3 to 5 short bullets - the words that actually appear. Keep "
        "each under 10 words; no sentences on a slide.\n"
        "- 'Visual:' what the slide should show (diagram, screenshot, table) in one line.\n"
        "- 'Speaker notes:' 3 to 5 sentences of what I say, written the way I would "
        "say it out loud.\n"
        "- 'Timing:' approximate minutes.\n\n"
        "Open with a hook slide and an agenda slide; close with a summary slide and "
        "a 'what to do next' slide. Put the deepest technical content in the middle "
        "third. The timings must sum to the talk length."
        + _grounding(context)
    )


def diagram(area, version, level, kind, subject, detail, context=""):
    return (
        f"Produce a technical diagram and the narrative to explain it while teaching.\n\n"
        f"{_ctx(area, version, level)} Diagram type: {_clean(kind, 'architecture')}.\n"
        f"What to draw: {_clean(subject, area)}.\n"
        f"{('Extra requirements: ' + detail.strip()) if _clean(detail) else ''}\n\n"
        "Produce, in this order:\n"
        "1. '# ' a title for the diagram.\n"
        "2. '## Diagram' - a SINGLE fenced code block tagged ```mermaid containing "
        "valid Mermaid. Rules for the Mermaid block, follow them exactly or it will "
        "not render:\n"
        "   - Choose the right Mermaid type: 'flowchart TD' or 'flowchart LR' for "
        "architecture, topology and decision flows; 'sequenceDiagram' for call "
        "flows; 'stateDiagram-v2' for state machines; 'gantt' for phased plans; "
        "'erDiagram' for data models; 'mindmap' for mind maps.\n"
        "   - Node ids must be simple alphanumeric tokens (vc1, esxi2). Put the "
        "human label in square brackets: vc1[vCenter Server].\n"
        "   - Never put parentheses, braces, colons, slashes, quotes or a trailing "
        "period inside a node label - they break the parser. Write 'vSAN ESA' not "
        "'vSAN (ESA)'.\n"
        "   - To group things use 'subgraph sg1[Group Label]' ... 'end'. The "
        "subgraph id must be a single alphanumeric token with NO spaces - "
        "'subgraph Management Domain[...]' is a parse error.\n"
        "   - Edge labels are written '-->|manages|' with no spaces beside the "
        "pipes. Keep the whole diagram to at most 20 nodes so it stays readable "
        "on a slide.\n"
        "   - Do not add styling, classDefs, comments or blank lines.\n"
        "3. '## What each part does' - a table of Component | Role | Why it matters.\n"
        "4. '## How I explain this' - the walkthrough narrative, in the order I "
        "should trace the diagram while presenting, as numbered steps.\n"
        "5. '## Traffic / data flow' - what moves between the components, and over "
        "which ports or protocols where that is known.\n"
        "6. '## Design considerations' - sizing, availability, failure domains and "
        "the trade-off an architect must decide."
        + _grounding(context)
    )


def explainer(area, version, topic, tone, audience, context=""):
    return (
        f"Explain one technical concept at four increasing depths, so I can pitch it "
        f"to any room.\n\n{_ctx(area, version, '', audience)} "
        f"Concept: {_clean(topic, area)}. Style: {_clean(tone, 'practical and concise')}.\n\n"
        "Produce:\n"
        "1. '# ' the concept name, then a one-sentence definition a non-specialist "
        "would understand.\n"
        "2. '## The analogy' - one everyday analogy, then explicitly state where the "
        "analogy breaks down (this is the part people skip and it matters).\n"
        "3. '## L100 - what it is' - the awareness-level explanation, 120 words.\n"
        "4. '## L200 - how it works' - the practitioner explanation, including the "
        "moving parts and a small example.\n"
        "5. '## L300 - how it really works' - the mechanism underneath: the "
        "components involved, the sequence of events, the limits and defaults.\n"
        "6. '## L400 - what an architect worries about' - failure modes, scale "
        "limits, interactions with other features, and the design trade-off.\n"
        "7. '## Whiteboard version' - the five things I draw, in order.\n"
        "8. '## Getting it wrong' - the misconception, why it is tempting, and what "
        "actually happens as a result."
        + _grounding(context)
    )


# =============================================================================
#  Hands-on
# =============================================================================
def lab_guide(area, version, level, topic, duration, environment, solution, context=""):
    return (
        f"Write a hands-on lab guide a learner can follow unattended.\n\n"
        f"{_ctx(area, version, level)} Lab topic: {_clean(topic, area)}. "
        f"Time budget: {_clean(duration, '45 minutes')}. "
        f"Environment: {_clean(environment, 'not specified')}.\n\n"
        "Produce:\n"
        "1. '# ' lab title, then 'Objective:' one line, and 'Time:' the budget.\n"
        "2. '## Before you start' - prerequisites, the exact environment state "
        "assumed, credentials/roles needed, and anything to download.\n"
        "3. '## Tasks' - a '### Task N - <name>' per task, each with numbered steps. "
        "Every step is one action. Commands go in fenced code blocks with the right "
        "language tag. After each task add a '**Checkpoint:**' line stating exactly "
        "what the learner should now see, so they can self-verify before moving on.\n"
        "4. '## If it does not work' - a table of Symptom | Likely cause | Fix, "
        "covering the three failures that actually happen in this lab.\n"
        "5. '## Clean up' - how to return the environment to its starting state, "
        "so the pod can be reused.\n"
        "6. '## Going further' - two optional challenge tasks, stated as goals "
        "without steps.\n"
        + ("7. '## Instructor solution key' - the expected commands, values and "
           "outputs for every task, plus the answers to the challenge tasks. Mark "
           "this section clearly as instructor-only.\n" if solution else
           "Do NOT include a solution key - this copy is for the learner.\n")
        + "Fit the whole lab inside the time budget; say how long each task should take."
        + _grounding(context)
    )


def demo_runbook(area, version, topic, duration, environment, context=""):
    return (
        f"Write a live-demo runbook for me to drive from, on stage, without notes.\n\n"
        f"{_ctx(area, version, '')} Demo: {_clean(topic, area)}. "
        f"Time on stage: {_clean(duration, '15 minutes')}. "
        f"Environment: {_clean(environment, 'not specified')}.\n\n"
        "Produce:\n"
        "1. '# ' demo title, then 'The point of this demo:' one sentence - the single "
        "idea the audience must take away.\n"
        "2. '## Pre-flight' - a checklist to run BEFORE the session: environment "
        "state, tabs to open, windows to arrange, things to pre-warm, what to reset "
        "from the last run. Format as checkbox bullets '- [ ] '.\n"
        "3. '## The run' - numbered steps. Each step has the exact command or click "
        "path in a code block, what the audience will see, and - in italics - the "
        "line I say while it happens. Mark any step that takes more than 20 seconds "
        "with how long it takes and what to talk about meanwhile.\n"
        "4. '## Where it usually breaks' - a table of What breaks | Why | Recovery "
        "in under 30 seconds.\n"
        "5. '## Plan B' - what to do if the environment is unavailable: the "
        "screenshots or narrative to fall back on, so the session continues.\n"
        "6. '## Reset' - how to return the environment to demo-ready state.\n"
        "Keep the run inside the stage time with a two-minute buffer."
        + _grounding(context)
    )


def troubleshooting(area, version, level, symptom, difficulty, context=""):
    return (
        f"Build a troubleshooting scenario I can run as a classroom exercise.\n\n"
        f"{_ctx(area, version, level)} Fault area / symptom to build around: "
        f"{_clean(symptom, area)}. Difficulty: {_clean(difficulty, 'moderate')}.\n\n"
        "Produce:\n"
        "1. '# ' scenario title.\n"
        "2. '## The ticket' - the scenario as a realistic support ticket or user "
        "complaint: what was reported, when it started, what changed recently. Keep "
        "the root cause hidden.\n"
        "3. '## What the learner can see' - the symptoms, error messages and log "
        "lines available to them, in code blocks. Include at least one red herring "
        "that looks relevant but is not.\n"
        "4. '## Guided diagnosis' - the questions to work through in order, each "
        "with the command or check that answers it, and how to read the result. This "
        "is the method, not the answer.\n"
        "5. '## Root cause' - what was actually wrong, and the chain from cause to "
        "symptom. Explain why the red herring misleads.\n"
        "6. '## The fix' - the remediation steps, and how to confirm it is resolved.\n"
        "7. '## Preventing it' - the monitoring, config or process change that stops "
        "it recurring.\n"
        "8. '## Teaching notes' - what to reveal and when, and the hint to give a "
        "learner who is stuck for more than ten minutes."
        + _grounding(context)
    )


# =============================================================================
#  Practice & Assess
# =============================================================================
def quiz(area, version, level, topic, fmt, count, certification, context=""):
    exam = _clean(certification)
    exam_line = ""
    if exam and not exam.startswith("—"):
        exam_line = (f"Target certification: {exam}. Match that exam's style, depth "
                     "and phrasing, and stay inside its published blueprint. Do not "
                     "reproduce real exam questions - write original ones. ")
    return (
        f"Write an assessment.\n\n{_ctx(area, version, level)} "
        f"Topic: {_clean(topic, area)}. Question style: {_clean(fmt, 'multiple choice')}. "
        f"Number of questions: {_clean(count, '10')}. {exam_line}\n\n"
        "Produce:\n"
        "1. '# ' the quiz title, then a line stating the topic, level and how long "
        "it should take.\n"
        "2. '## Questions' - numbered. Each question is a realistic problem, not a "
        "definition lookup: put it in a situation ('A cluster shows... What is the "
        "most likely cause?'). Where the style calls for options, label them A/B/C/D "
        "on their own lines. Never hint at the answer through option length or "
        "wording, and avoid 'all of the above'.\n"
        "3. '## Answer key' - a '### Q<n>' per question with: the correct answer, "
        "two to three sentences on WHY it is correct, and one line per wrong option "
        "explaining precisely why it is wrong. The distractor explanations are the "
        "most valuable part - make them teach.\n"
        "4. '## Coverage' - a table of Question | Sub-topic | Level, so I can see "
        "the blueprint balance at a glance.\n"
        "Spread difficulty: roughly a quarter easy, half moderate, a quarter hard."
        + _grounding(context)
    )


def flashcards(area, version, level, topic, count, context=""):
    return (
        f"Write revision flashcards.\n\n{_ctx(area, version, level)} "
        f"Topic: {_clean(topic, area)}. Number of cards: {_clean(count, '20')}.\n\n"
        "Produce:\n"
        "1. '# ' the deck title, then one line on what it covers.\n"
        "2. '## Cards' - a single Markdown table with exactly three columns: "
        "Front | Back | Tag. One row per card, nothing else in the section.\n"
        "   - Front: a question or a term. One idea per card, never two.\n"
        "   - Back: the answer in under 25 words. Precise, no padding. Include the "
        "number, default or command where that is the thing worth remembering.\n"
        "   - Tag: the sub-topic, one or two words, no spaces around it.\n"
        "   - Do not use the pipe character inside any cell.\n"
        "3. '## Hardest five' - the five cards learners most often get wrong, each "
        "with a one-line memory hook.\n"
        "Cover the topic evenly rather than clustering on one sub-area."
        + _grounding(context)
    )


def study_plan(certification, weeks, hours, level, background, context=""):
    return (
        f"Write a certification study plan.\n\n"
        f"Target exam: {_clean(certification, 'the stated certification')}. "
        f"Time available: {_clean(weeks, '8 weeks')}, about "
        f"{_clean(hours, '6 hours')} per week. "
        f"Starting point: {_clean(background, 'some hands-on experience with the platform')}. "
        f"{('Current depth: ' + level) if _clean(level) else ''}\n\n"
        "Produce:\n"
        "1. '# ' the plan title, then 'Exam:' the code and name, 'Format:' what the "
        "exam looks like (question count, duration, passing approach) - mark anything "
        "you are unsure of with [verify], since exam details change.\n"
        "2. '## Blueprint coverage' - a table of Domain | Weight | Weeks allocated. "
        "Weight the schedule by the exam's published domain weightings.\n"
        "3. '## Week by week' - a '### Week N' per week with: the topics, the "
        "hands-on lab to build that week, the practice to do, and a one-line "
        "checkpoint that says whether the week landed.\n"
        "4. '## Lab you should build' - the single environment worth building for "
        "this exam, and what to run on it.\n"
        "5. '## Resources' - official documentation and study material by name and "
        "type. Only name resources you are confident exist; do not invent URLs.\n"
        "6. '## Final two weeks' - the revision and mock-exam routine.\n"
        "7. '## Exam-day tactics' - time management and how to handle the question "
        "types that eat the clock.\n"
        "Keep the weekly load inside the stated hours. Be honest if the timeframe is "
        "unrealistic and say what to drop."
        + _grounding(context)
    )


# =============================================================================
#  Code & Config
# =============================================================================
def script(area, language, task, level, version, requirements, context=""):
    return (
        f"Write a teaching-quality script.\n\n{_ctx(area, version, level)} "
        f"Language / tool: {_clean(language, 'PowerShell')}.\n"
        f"What it must do: {_clean(task)}.\n"
        f"{('Additional requirements: ' + requirements.strip()) if _clean(requirements) else ''}\n\n"
        "Produce:\n"
        "1. '# ' a name for the script, then one line on what it does and who runs it.\n"
        "2. '## Before you run it' - modules or providers required, permissions "
        "needed, and what it will change.\n"
        "3. '## The script' - one fenced code block with the correct language tag. "
        "The code must be complete and runnable, with: a header comment block, "
        "parameters at the top rather than hard-coded values, input validation, "
        "error handling, and a comment above each logical block explaining the "
        "reasoning - not restating the syntax.\n"
        "4. '## Line by line' - walk through the script in blocks, explaining what "
        "each does and why it is written that way. This is the teaching section.\n"
        "5. '## Running it' - the invocation with example arguments, in a code "
        "block, plus what a successful run looks like.\n"
        "6. '## Safety' - what to test first, how to dry-run it, and what to do if "
        "it is interrupted half way.\n"
        "7. '## Make it your own' - three extensions a learner can attempt.\n"
        "Idempotent where the task allows. Never delete anything without an explicit "
        "confirmation prompt or a -WhatIf/--dry-run equivalent."
        + _grounding(context)
    )


def code_explain(language, code, level, focus, context=""):
    return (
        f"Explain this code so I can teach from it.\n\n"
        f"Language / format: {_clean(language, 'as written')}. "
        f"Audience depth: {_clean(level, 'L200 - practitioner')}.\n"
        f"{('Focus on: ' + focus.strip()) if _clean(focus) else ''}\n\n"
        "Here is the code:\n\n```\n" + (code or "")[:8000] + "\n```\n\n"
        "Produce:\n"
        "1. '# ' a title naming what this code does.\n"
        "2. '## In one paragraph' - what it does, for someone who will never read "
        "the code.\n"
        "3. '## How it flows' - the execution path as numbered steps.\n"
        "4. '## Section by section' - the code split into logical chunks. For each: "
        "the chunk in a fenced code block, then what it does and why it is written "
        "that way. Explain the intent, not the syntax.\n"
        "5. '## Concepts to teach here' - the transferable ideas this code is a good "
        "vehicle for, and the order to introduce them.\n"
        "6. '## Issues and improvements' - correctness, error handling, security and "
        "performance concerns, each with the specific line or construct at fault and "
        "the better way. Say plainly if the code is fine.\n"
        "7. '## Questions to ask learners' - four questions that check they actually "
        "understood it, with the answers.\n"
        "Describe only what is in the code. If something is ambiguous or depends on "
        "code not shown, say so rather than guessing."
        + _grounding(context)
    )


def cheat_sheet(area, version, topic, audience, tone, context=""):
    return (
        f"Write a one-page cheat sheet I can print and hand out.\n\n"
        f"{_ctx(area, version, '', audience)} Topic: {_clean(topic, area)}. "
        f"Style: {_clean(tone, 'practical and concise')}.\n\n"
        "Produce:\n"
        "1. '# ' the cheat sheet title, then one line on scope and version.\n"
        "2. Four to seven '## ' sections grouped by the task the engineer is trying "
        "to do (Check health, Configure, Troubleshoot, Recover), NOT alphabetically.\n"
        "3. In each section, a table with columns Task | Command | Notes. The "
        "command goes in inline backticks. Notes carry the flag that matters, the "
        "gotcha, or the safe alternative - keep to one short line.\n"
        "4. '## Key values to remember' - a table of defaults, limits, ports and "
        "paths worth memorising. Mark anything version-dependent with [verify].\n"
        "5. '## Danger zone' - the commands that are destructive or "
        "service-affecting, and what to check before running each.\n"
        "Dense and scannable. This must fit on one printed page, so no prose "
        "paragraphs and no repetition."
        + _grounding(context)
    )


# =============================================================================
#  Deliver & Publish
# =============================================================================
def handout(area, version, level, topic, covered, context=""):
    return (
        f"Write the take-away notes I give learners after the session.\n\n"
        f"{_ctx(area, version, level)} Session topic: {_clean(topic, area)}.\n"
        f"{('What was covered: ' + covered.strip()) if _clean(covered) else ''}\n\n"
        "Produce:\n"
        "1. '# ' the handout title, then 'Session:' the topic and 'Level:' the depth.\n"
        "2. '## The five things to remember' - a numbered list, one line each. If "
        "they read nothing else, this is it.\n"
        "3. '## What we covered' - the concepts, explained properly enough to be "
        "useful weeks later. Written for reading alone, not as slide bullets.\n"
        "4. '## Commands and settings from the session' - a table of Purpose | "
        "Command / setting | Note.\n"
        "5. '## Try this on your own' - three practice tasks of increasing "
        "difficulty, with what 'done' looks like for each.\n"
        "6. '## Going deeper' - what to read or build next, and in what order.\n"
        "7. '## Glossary' - a table of the terms used, each defined in one line.\n"
        "Written to be self-contained - it must make sense without the slides."
        + _grounding(context)
    )


def runbook(area, version, procedure, environment, audience, context=""):
    return (
        f"Write an operational runbook / standard operating procedure.\n\n"
        f"{_ctx(area, version, '', audience)} Procedure: {_clean(procedure)}. "
        f"Environment: {_clean(environment, 'production')}.\n\n"
        "Produce:\n"
        "1. '# ' the procedure name, then a table of Purpose | Owner | Risk level | "
        "Expected duration | Downtime required.\n"
        "2. '## When to use this' - the trigger, and explicitly when NOT to use it.\n"
        "3. '## Prerequisites' - access and roles required, change-approval needed, "
        "backups or snapshots to take first, and the maintenance window.\n"
        "4. '## Pre-checks' - checkbox bullets '- [ ] ' with the command that proves "
        "each one, and the value that means 'safe to proceed'.\n"
        "5. '## Procedure' - numbered steps. One action per step, exact commands in "
        "code blocks, expected result stated after each. Mark every irreversible or "
        "service-affecting step with a bold warning line before it, and give the "
        "point of no return explicitly.\n"
        "6. '## Validation' - how to prove it worked, at the infrastructure level "
        "and at the service/user level.\n"
        "7. '## Rollback' - the steps to reverse it, how long rollback takes, and "
        "the deadline after which rollback is no longer possible.\n"
        "8. '## Troubleshooting' - a table of Symptom | Cause | Action.\n"
        "9. '## Record' - what to log or attach to the change ticket afterwards.\n"
        "Written so a competent engineer who has never done this can execute it "
        "safely at 2am."
        + _grounding(context)
    )


def article(area, version, topic, angle, length, tone, context=""):
    return (
        f"Draft a technical article for drpranayjha.com - the Journal of Intelligent "
        f"Infrastructure.\n\n{_ctx(area, version, '')} Subject: {_clean(topic, area)}.\n"
        f"{('Angle / argument: ' + angle.strip()) if _clean(angle) else ''}\n"
        f"Target length: {_clean(length, '900 words')}. Tone: "
        f"{_clean(tone, 'practical and concise')}.\n\n"
        "Produce:\n"
        "1. '# ' a title that states the value, not a pun. Then a one-line standfirst.\n"
        "2. An opening that starts from a real problem an engineer has hit - no "
        "throat-clearing, no 'in this article we will'.\n"
        "3. '## ' sections carrying the argument. Include at least one table or code "
        "block where it earns its place. Where there is a trade-off, present both "
        "sides and then take a clear position.\n"
        "4. '## What I would do' - the recommendation, stated plainly, with the "
        "conditions under which it changes.\n"
        "5. '## Takeaways' - three to five bullets.\n"
        "6. A closing line inviting discussion, and then a '---' rule followed by "
        "'Suggested tags:' a comma-separated list, and 'Suggested meta description:' "
        "one sentence under 155 characters.\n"
        "Write in first person as Dr Pranay Jha. Opinionated, evidence-led, no "
        "vendor marketing tone."
        + _grounding(context)
    )


def comms(kind, topic, audience, details, tone, context=""):
    return (
        f"Write a training communication.\n\n"
        f"Type: {_clean(kind, 'announcement')}. Subject: {_clean(topic)}. "
        f"Audience: {_clean(audience, 'course participants')}. "
        f"Tone: {_clean(tone, 'practical and concise')}.\n"
        f"{('Details to include: ' + details.strip()) if _clean(details) else ''}\n\n"
        "Produce:\n"
        "1. '# ' an internal label for this message (not part of the message itself).\n"
        "2. '## Subject line' - three options, each under 60 characters.\n"
        "3. '## Message' - the message itself, ready to send. Short paragraphs, the "
        "ask or action in the first three lines, and any logistics (date, time, "
        "duration, joining link placeholder, prerequisites) in a clear block rather "
        "than buried in prose. Use a checklist where the reader must prepare "
        "something.\n"
        "4. '## Short version' - the same message in under 60 words, for WhatsApp or "
        "a chat channel.\n"
        "5. '## LinkedIn version' - a public post version if the topic suits one, "
        "with a hook first line, three to five short paragraphs and no hashtag spam. "
        "Omit this section entirely if the message is internal or private.\n"
        "Use placeholders in angle brackets for anything not supplied "
        "(<date>, <joining link>). Never invent a date, price or link."
        + _grounding(context)
    )
