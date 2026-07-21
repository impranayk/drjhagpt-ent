"""Render generated Markdown into a styled, on-brand technical document.

Matches drpranayjha.com: white editorial surface, charcoal ink, red accent,
Inter for text and Oswald for headings, with a monospace treatment for code.

Three things this does that a plain st.markdown call does not:
  * per-section line icons chosen from the heading text (no OS emoji),
  * first-class code blocks - language chip, syntax highlighting, print-safe,
  * Mermaid diagrams, rendered live in the app and in the downloaded file.

The same CSS (DOC_CSS) is used in-app and in the downloadable/printable file.
"""
import html as _hh
import re

import markdown as _md

# --- Brand tokens (kept in sync with chatbot/config.py) ---
INK = "#141618"
ACCENT = "#ce242c"
MUTED = "#5f5e5a"
BORDER = "#e7e7e7"
PANEL = "#f5f5f5"

FOOTER_LEFT = "Dr. Pranay Jha · Journal of Intelligent Infrastructure"
FOOTER_RIGHT = "drpranayjha.com"


def _svg(paths: str) -> str:
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + paths + '</svg>')


# Section icons, matched on keywords in the heading. First match wins, so the
# more specific entries are listed first.
_ICONS = [
    (("danger", "warning", "caution", "destructive", "risk", "blast radius"),
     _svg('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
          '<path d="M12 9v4M12 17h.01"/>')),
    (("rollback", "roll back", "revert", "undo", "reset", "clean up", "cleanup"),
     _svg('<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>')),
    (("checkpoint", "validat", "verify", "confirm", "pre-check", "precheck",
      "how to prove", "success"),
     _svg('<circle cx="12" cy="12" r="9"/><path d="M8 12.2l2.6 2.6L16 9.4"/>')),
    (("troubleshoot", "if it does not work", "does not work", "breaks", "symptom",
      "root cause", "issues", "diagnos", "failure"),
     _svg('<circle cx="11" cy="11" r="7"/><path d="M20 20l-4.3-4.3"/><path d="M11 8v3M11 14h.01"/>')),
    (("command", "cli", "run", "the script", "invocation", "syntax", "terminal",
      "code", "snippet"),
     _svg('<rect x="2.5" y="4" width="19" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>')),
    (("prereq", "before you", "pre-flight", "preflight", "requirement", "setup",
      "environment", "you will need", "lab environment"),
     _svg('<path d="M4 20h16"/><rect x="5" y="4" width="6" height="10" rx="1"/>'
          '<rect x="13" y="8" width="6" height="6" rx="1"/>')),
    (("objective", "outcome", "goal", "the point", "purpose", "aim", "takeaway",
      "remember", "what we covered"),
     _svg('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.2"/>')),
    (("architecture", "diagram", "component", "topology", "flow", "design",
      "data flow", "traffic"),
     _svg('<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>'
          '<path d="M6.5 10v5.5a1 1 0 0 0 1 1H14"/>')),
    (("security", "hardening", "permission", "access", "safety", "credential"),
     _svg('<path d="M12 3l7.5 3.2v5.6c0 4.4-3.2 7.9-7.5 9.2-4.3-1.3-7.5-4.8-7.5-9.2V6.2z"/>'
          '<path d="M9.3 12.2l1.9 1.9 3.6-3.8"/>')),
    (("procedure", "the run", "task", "step", "how i explain", "walkthrough",
      "line by line", "section by section"),
     _svg('<path d="M8 5h12M8 12h12M8 19h12"/><circle cx="4" cy="5" r="1.4"/>'
          '<circle cx="4" cy="12" r="1.4"/><circle cx="4" cy="19" r="1.4"/>')),
    (("question", "quiz", "answer key", "ask", "viva", "faq", "likely question"),
     _svg('<circle cx="12" cy="12" r="9"/><path d="M9.4 9.2a2.7 2.7 0 1 1 3.4 3.2c-.7.3-.9.8-.9 1.5"/>'
          '<path d="M12 17.4h.01"/>')),
    (("schedule", "run sheet", "timing", "week", "day ", "at a glance", "agenda",
      "plan", "timeline", "duration"),
     _svg('<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>')),
    (("coverage", "blueprint", "table", "matrix", "comparison", "summary"),
     _svg('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 10h17M9.5 10v9.5"/>')),
    (("slide", "deck", "present", "talking track", "narrative", "speaker"),
     _svg('<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M12 16v4M8.5 20h7"/>')),
    (("resource", "further", "going deeper", "next", "read", "glossary", "reference"),
     _svg('<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5z"/>'
          '<path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H19v3H6.5A2.5 2.5 0 0 0 4 20.5z"/>')),
    (("misconception", "getting it wrong", "gotcha", "mistake", "myth", "teaching note",
      "instructor"),
     _svg('<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 16.5h.01"/>')),
    (("card", "flashcard", "revision", "front", "hardest"),
     _svg('<rect x="2.5" y="6" width="14" height="12" rx="2"/><path d="M7 3h14v12"/>')),
    (("analogy", "l100", "l200", "l300", "l400", "whiteboard", "explain", "concept"),
     _svg('<path d="M9 18h6"/><path d="M10 21h4"/>'
          '<path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5.9 1.2.9 2h5.2c0-.8.3-1.5.9-2A6 6 0 0 0 12 3z"/>')),
]
_DEFAULT = _svg('<circle cx="12" cy="12" r="9"/><path d="M12 8.4v4.2M12 16h.01"/>')


def _icon_for(title: str) -> str:
    t = re.sub(r"<[^>]+>", "", title or "").lower()
    for keys, svg in _ICONS:
        if any(k in t for k in keys):
            return svg
    return _DEFAULT


# =============================================================================
#  Markdown normalisation
# =============================================================================
_FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9+#_-]*)[ \t]*\n(.*?)(?:```|\Z)", re.S)


def _protect_fences(md: str):
    """Pull fenced code out before normalising, so prose rules never touch code."""
    blocks = []

    def _stash(m):
        blocks.append((m.group(1) or "", m.group(2)))
        return f"\x00FENCE{len(blocks) - 1}\x00"

    return _FENCE_RE.sub(_stash, md or ""), blocks


def _restore_fences(md: str, blocks) -> str:
    for i, (lang, body) in enumerate(blocks):
        md = md.replace(f"\x00FENCE{i}\x00",
                        f"```{lang}\n{body.rstrip()}\n```")
    return md


def _normalize(md: str) -> str:
    """Rescue structure the model wrote loosely, so it renders as intended.

    Code is protected first: a hyphen or asterisk inside a shell command must
    never be rewritten into a list item.
    """
    if not md:
        return md
    md, fences = _protect_fences(md)

    # House style is a plain hyphen: fold em / en dashes the model slipped in.
    md = md.replace("—", "-").replace("–", "-")
    # Non-breaking and narrow spaces defeat the [ \t] rules below.
    md = re.sub(r"[   ﻿]", " ", md)
    # A number-dot mid-line that starts a list item -> its own line.
    md = re.sub(r'([^\n])[ \t]+(\d{1,2})\.[ \t]+(?=[A-Z*"\'(])', r'\1\n\2. ', md)
    # An inline "- " / "* " bullet after a colon or sentence -> its own line.
    md = re.sub(r'([:.\)])[ \t]+[*-][ \t]+(?=[A-Za-z"\'])', r'\1\n- ', md)
    # A "- **Label:**" bullet whose text was pushed to the next indented line ->
    # pull it back so label and text render as one flat item.
    md = re.sub(r'(?m)^([ \t]*[-*])[ \t]+(\*\*[^*\n]+?:\*\*)[ \t]*\n[ \t]+[-*][ \t]+',
                r'\1 \2 ', md)
    md = re.sub(r'(?m)^([ \t]*[-*])[ \t]+(\*\*[^*\n]+?:\*\*)[ \t]*\n[ \t]+(?=\S)',
                r'\1 \2 ', md)
    # Markdown lazily joins adjacent lines into one paragraph, which merges a
    # "**Checkpoint:**" line into the bullet above it. Force a blank line before
    # any line that starts with a short bold label.
    md = re.sub(r'([^\n])\n(?=[ \t]*\*\*[^*\n]{1,44}:\*\*)', r'\1\n\n', md)
    # A line that is ENTIRELY one bold span is a heading the model wrote as bold.
    # Promote it so it gets the section icon and accent rule.
    md = re.sub(r'(?m)^[ \t]*\*\*([^*\n]{2,80}?):?\*\*[ \t]*$', r'\n## \1\n', md)
    # Drop empty headings that would render as blank banners.
    md = re.sub(r'(?m)^[ \t]*#{1,6}[ \t]*$\n?', '', md)
    # Ensure a blank line before a list that immediately follows a paragraph.
    md = re.sub(r'([^\n])\n(\d{1,2}\.[ \t])', r'\1\n\n\2', md)
    md = re.sub(r'([^\n])\n([-*][ \t])', r'\1\n\n\2', md)
    # Checkbox bullets ("- [ ] ") are used by pre-flight and pre-check sections.
    md = re.sub(r'(?m)^([ \t]*)-[ \t]\[[ xX]\][ \t]+', r'\1- ', md)

    return _restore_fences(md, fences)


# =============================================================================
#  Code + Mermaid extraction
# =============================================================================
_MERMAID_TYPES = ("flowchart", "graph", "sequencediagram", "statediagram",
                  "erdiagram", "gantt", "mindmap", "journey", "classdiagram",
                  "pie", "timeline")


def code_blocks(md: str, exclude_mermaid: bool = True):
    """Every fenced block as (language, source), for the 'Copy code' action."""
    out = []
    for lang, body in _FENCE_RE.findall(md or ""):
        if exclude_mermaid and lang.lower() == "mermaid":
            continue
        out.append((lang.lower(), body.rstrip()))
    return out


def mermaid_blocks(md: str):
    """Every Mermaid diagram source in the document."""
    return [b.strip() for lang, b in _FENCE_RE.findall(md or "")
            if lang.lower() == "mermaid"]


def clean_mermaid(src: str) -> str:
    """Repair the Mermaid mistakes models make most often.

    Mermaid fails hard on a syntax error - it renders nothing at all - so a few
    conservative fixes are worth far more than a perfect parse.
    """
    s = (src or "").strip()
    if not s:
        return ""
    s = re.sub(r"^```[a-z]*\s*|\s*```$", "", s).strip()
    lines = []
    for ln in s.splitlines():
        # Strip trailing semicolons and stray comment markers.
        ln = re.sub(r"\s*;\s*$", "", ln.rstrip())
        if not ln.strip() or ln.strip().startswith("%%"):
            continue
        # 'subgraph Management Domain[Label]' - an id containing spaces is a parse
        # error, and it is the mistake models make most. Slugify the id, keep the
        # label. ('subgraph Some Title' with no bracket is valid, so it is left.)
        ln = re.sub(
            r"(?i)^(\s*subgraph\s+)([^\[\]\n]*\s[^\[\]\n]*?)\s*\[",
            lambda m: m.group(1) + re.sub(r"[^A-Za-z0-9]", "", m.group(2))[:24] + "[",
            ln)
        # Parentheses, braces, quotes and pipes inside a [Label] break the parser.
        def _fix_label(m):
            inner = m.group(2)
            inner = inner.replace("(", " ").replace(")", " ")
            inner = inner.replace("{", " ").replace("}", " ")
            inner = inner.replace('"', "").replace("|", "/")
            inner = re.sub(r"\s{2,}", " ", inner).strip().rstrip(".")
            return f"{m.group(1)}[{inner}]"

        ln = re.sub(r"(\w)\[([^\[\]\n]*)\]", _fix_label, ln)
        # Edge labels: '-->| manages |' is tolerated, but the padded form trips
        # some versions. Normalise to the canonical '-->|manages|'.
        ln = re.sub(r"\|\s+([^|\n]*?)\s+\|", r"|\1|", ln)
        # '-->|manages|> nsx1' - the model closes the label and then repeats the
        # arrowhead. Observed live; it is a parse error, so the whole diagram
        # renders as nothing.
        ln = re.sub(r"\|\s*>", "|", ln)
        # A line that STARTS with an arrow has no source node ('-->|connect to| vc1').
        # Also observed live. There is nothing to infer, so drop the statement
        # rather than let it kill every other node in the diagram.
        if re.match(r"^\s*(-{2,}>|-{3,}|-\.->|={2,}>|~~~)", ln):
            continue
        lines.append(ln)
    s = "\n".join(lines).strip()
    if not s:
        return ""
    # If the first line isn't a diagram declaration, assume a top-down flowchart.
    first = s.splitlines()[0].strip().lower()
    if not first.startswith(_MERMAID_TYPES):
        s = "flowchart TD\n" + s
    return s


# =============================================================================
#  Markdown -> HTML
# =============================================================================
_ALLOWED_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "ul", "ol", "li",
                 "blockquote", "code", "pre", "em", "strong", "b", "i", "u", "del",
                 "hr", "br", "table", "thead", "tbody", "tr", "th", "td", "span",
                 "div", "svg", "circle", "path", "rect"]
_ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "code": ["class"], "pre": ["class"], "span": ["class"], "div": ["class"],
    "svg": ["viewbox", "viewBox", "fill", "stroke", "stroke-width",
            "stroke-linecap", "stroke-linejoin"],
    "path": ["d"], "circle": ["cx", "cy", "r"],
    "rect": ["x", "y", "width", "height", "rx"],
}


def _md_to_html(md: str) -> str:
    """Markdown -> HTML, sanitised so nothing from the model or a pasted note can
    execute. Falls back to the unsanitised HTML only if bleach is missing.

    Deliberately uses `fenced_code` WITHOUT `codehilite`: codehilite consumes the
    language tag to pick a lexer and then drops it, which loses both the language
    chip and the ability to find Mermaid blocks. Highlighting is applied
    afterwards, in `_highlight`, which keeps the tag.
    """
    raw = _md.markdown(_normalize(md) or "",
                       extensions=["tables", "sane_lists", "fenced_code"])
    try:
        import bleach
        return bleach.clean(raw, tags=set(_ALLOWED_TAGS), attributes=_ALLOWED_ATTRS,
                            protocols=["http", "https", "mailto"], strip=True)
    except ImportError:
        return raw


_CODE_RE = re.compile(
    r'<pre><code(?: class="(?:language-)?([A-Za-z0-9+#_-]+)")?>(.*?)</code></pre>',
    re.S)

# Markdown language tags -> Pygments lexer names, where they differ.
_LEXERS = {"powershell": "powershell", "posh": "powershell", "ps1": "powershell",
           "shell": "bash", "sh": "bash", "console": "console", "hcl": "terraform",
           "tf": "terraform", "yml": "yaml", "jsonc": "json", "text": "text",
           "plaintext": "text", "output": "text"}


def _highlight(html: str) -> str:
    """Give each fenced block its language chip, and colour it with Pygments.

    Runs after sanitising: the input is HTML this module generated, and Pygments
    escapes whatever it is handed, so nothing unescaped reaches the browser.
    """
    try:
        from pygments import highlight as _hl
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name
        formatter = HtmlFormatter(nowrap=True)
    except ImportError:
        _hl = None

    def _one(m):
        lang = (m.group(1) or "").lower()
        source = _hh.unescape(m.group(2))
        if lang == "mermaid":
            return '<pre class="mermaid">' + _hh.escape(source) + "</pre>"
        body = _hh.escape(source)
        if _hl and lang:
            try:
                lexer = get_lexer_by_name(_LEXERS.get(lang, lang), stripall=False)
                body = _hl(source, lexer, formatter).rstrip("\n")
            except Exception:
                pass                          # unknown lexer -> plain, escaped
        chip = f' data-lang="{_hh.escape(lang)}"' if lang else ""
        cls = "dj-code codehilite" if (_hl and lang) else "dj-code"
        return (f'<pre class="{cls}"{chip}><code class="language-{_hh.escape(lang)}">'
                f"{body}</code></pre>")

    return _CODE_RE.sub(_one, html)


def _meta_row(meta: dict) -> str:
    """A Course · Trainer · Version · Date row - only the filled fields."""
    order = [("Course", "course"), ("Trainer", "trainer"),
             ("Version", "version"), ("Date", "date")]
    parts = [f'<span>{label}<b>{_hh.escape(str(meta.get(key)))}</b></span>'
             for label, key in order if meta and meta.get(key)]
    if not parts:
        return ""
    return '<div class="dj-meta">' + "".join(parts) + "</div>"


def _decorate(html: str, meta: dict = None) -> str:
    """Add section icons, highlighted code blocks and the optional meta row."""
    html = re.sub(
        r"<h2>(.*?)</h2>",
        lambda m: f'<h2><span class="sec-ico">{_icon_for(m.group(1))}</span>'
                  f'<span class="sec-t">{m.group(1)}</span></h2>',
        html, flags=re.S)
    html = _highlight(html)
    if meta is not None:
        html = re.sub(r"(</h1>)", lambda m: m.group(1) + _meta_row(meta),
                      html, count=1)
    return html


def to_document(md: str, logo_uri: str = "", meta: dict = None,
                eyebrow: str = "DrJhaGPT Pro") -> str:
    """Markdown -> a styled HTML document (Mermaid kept as <pre class="mermaid">)."""
    body = _decorate(_md_to_html(md), meta)
    head = (f'<div class="dj-dhead"><img class="dj-dlogo" src="{logo_uri}" alt="">'
            f'<span class="dj-dtag">{_hh.escape(eyebrow)}</span></div>'
            ) if logo_uri else ""
    foot = (f'<div class="dj-dfoot"><span><b>{FOOTER_LEFT}</b></span>'
            f'<span>{FOOTER_RIGHT}</span></div>')
    return f'<div class="dj-doc">{head}{body}{foot}</div>'


def doc_segments(md: str, logo_uri: str = "", meta: dict = None,
                 eyebrow: str = "DrJhaGPT Pro"):
    """The document split into renderable pieces, for the in-app view.

    Streamlit's Markdown surface cannot run the Mermaid script, so the app draws
    the HTML pieces with st.markdown and each diagram in its own component frame.
    Returns a list of ("html", str) and ("mermaid", source) tuples.
    """
    doc = to_document(md, logo_uri, meta, eyebrow)
    parts, pos = [], 0
    for m in re.finditer(r'<pre class="mermaid">(.*?)</pre>', doc, re.S):
        before = doc[pos:m.start()]
        if before.strip():
            parts.append(("html", before + "</div>"))
        parts.append(("mermaid", _hh.unescape(m.group(1))))
        pos = m.end()
        doc = doc  # (kept explicit: the remainder is re-wrapped below)
    rest = doc[pos:]
    if not parts:
        return [("html", doc)]
    if rest.strip():
        parts.append(("html", '<div class="dj-doc dj-doc-cont">' + rest))
    # Every html chunk after the first needs its own wrapper opened.
    fixed = []
    for i, (kind, val) in enumerate(parts):
        if kind == "html" and i and not val.lstrip().startswith("<div"):
            val = '<div class="dj-doc dj-doc-cont">' + val
        fixed.append((kind, val))
    return fixed


# =============================================================================
#  Styling — shared by the in-app view and the downloadable file
# =============================================================================
DOC_CSS = """
.dj-doc { background:#fff; border:1px solid """ + BORDER + """; border-radius:4px;
  padding:0 0 4px; box-shadow:0 2px 14px rgba(20,22,24,.06); overflow:hidden;
  -webkit-print-color-adjust:exact; print-color-adjust:exact;
  font-family:'Inter',-apple-system,'Segoe UI',Arial,sans-serif; color:""" + INK + """; }
.dj-doc.dj-doc-cont { border-top:0; border-radius:0 0 4px 4px; margin-top:-8px; }
.dj-dhead { display:flex; align-items:center; justify-content:space-between;
  padding:14px 26px 0; }
.dj-dlogo { height:26px; width:auto; border:0; }
.dj-dtag { color:""" + ACCENT + """; font-family:'Oswald',sans-serif; font-weight:600;
  font-size:10px; letter-spacing:1.6px; text-transform:uppercase; }
.dj-doc h1 { font-family:'Oswald',sans-serif; font-weight:700; font-size:23px;
  line-height:1.2; color:""" + INK + """; text-transform:uppercase; letter-spacing:.4px;
  margin:14px 26px 8px; padding-bottom:12px; border-bottom:3px solid """ + ACCENT + """; }
.dj-doc .dj-meta { display:flex; flex-wrap:wrap; gap:5px 26px; margin:0 26px 10px;
  padding:9px 14px; background:""" + PANEL + """; border-left:3px solid """ + ACCENT + """;
  font-size:11.5px; color:""" + MUTED + """; font-family:'Oswald',sans-serif;
  font-weight:500; letter-spacing:.5px; text-transform:uppercase; }
.dj-doc .dj-meta b { color:""" + INK + """; font-weight:600; margin-left:7px;
  letter-spacing:0; text-transform:none; font-family:'Inter',sans-serif; }
.dj-doc h2 { display:flex; align-items:center; gap:12px; font-family:'Oswald',sans-serif;
  font-weight:600; font-size:15px; text-transform:uppercase; letter-spacing:.7px;
  color:""" + INK + """; margin:1.7rem 26px .6rem; padding-bottom:8px;
  border-bottom:1px solid """ + BORDER + """; }
.dj-doc h2 .sec-ico { flex:0 0 auto; width:26px; height:26px; border-radius:3px;
  background:""" + PANEL + """; display:inline-flex; align-items:center; justify-content:center; }
.dj-doc h2 .sec-ico svg { width:15px; height:15px; color:""" + ACCENT + """; }
.dj-doc h3 { font-family:'Oswald',sans-serif; font-weight:600; font-size:13px;
  text-transform:uppercase; letter-spacing:.6px; color:""" + ACCENT + """;
  margin:1.25rem 26px .45rem; padding-left:11px; border-left:3px solid """ + ACCENT + """; }
.dj-doc h4 { font-family:'Inter',sans-serif; font-weight:700; font-size:13px;
  color:""" + INK + """; margin:1rem 26px .3rem; }
.dj-doc p, .dj-doc li { font-size:14px; line-height:1.72; }
.dj-doc p { margin:.5rem 26px; }
.dj-doc strong { font-weight:700; }
.dj-doc em { color:""" + MUTED + """; }
.dj-doc a { color:""" + ACCENT + """; text-decoration:none; border-bottom:1px solid #f0c4c6; }
.dj-doc ul, .dj-doc ol { margin:.5rem 26px; }
.dj-doc li > ul, .dj-doc li > ol { margin:.25rem 0 .25rem 4px; }
.dj-doc ul { list-style:none; padding-left:2px; }
.dj-doc ul li { position:relative; padding-left:17px; margin:5px 0; }
.dj-doc ul li::before { content:""; position:absolute; left:0; top:.62em; width:6px;
  height:6px; background:""" + ACCENT + """; }
.dj-doc ol { padding-left:0; list-style:none; counter-reset:step; }
.dj-doc ol li { position:relative; padding-left:32px; margin:7px 0; counter-increment:step; }
.dj-doc ol li::before { content:counter(step,decimal-leading-zero); position:absolute;
  left:0; top:.05em; font-family:'Oswald',sans-serif; font-weight:600; font-size:12px;
  color:""" + ACCENT + """; letter-spacing:.5px; }
.dj-doc blockquote { margin:.7rem 26px; padding:9px 15px; background:""" + PANEL + """;
  border-left:3px solid #c9c9c9; color:""" + MUTED + """; font-size:13.5px; }
.dj-doc table { border-collapse:collapse; width:calc(100% - 52px); margin:.7rem 26px;
  font-size:13px; border:1px solid """ + BORDER + """; }
.dj-doc th { background:""" + INK + """; color:#fff; font-family:'Oswald',sans-serif;
  font-weight:500; font-size:11.5px; letter-spacing:.7px; text-transform:uppercase;
  text-align:left; padding:9px 12px; }
.dj-doc td { padding:9px 12px; border-top:1px solid """ + BORDER + """; vertical-align:top; }
.dj-doc tbody tr:nth-child(even) { background:#fafafa; }
.dj-doc td code, .dj-doc p code, .dj-doc li code { background:""" + PANEL + """;
  border:1px solid #e3e3e3; border-radius:3px; padding:1px 5px; font-size:12.5px;
  font-family:'JetBrains Mono','Consolas','SFMono-Regular',monospace; color:#8a1b21; }
/* Code blocks - a dark panel with a language chip, print-safe. */
.dj-doc pre, .dj-doc .codehilite { position:relative; margin:.8rem 26px;
  background:#1b1e21; border-radius:4px; padding:15px 16px 14px; overflow-x:auto;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.dj-doc .codehilite pre { margin:0; padding:0; background:none; }
.dj-doc pre code { display:block; background:none; border:0; padding:0; color:#e6e6e6;
  font-family:'JetBrains Mono','Consolas','SFMono-Regular',monospace; font-size:12.5px;
  line-height:1.62; white-space:pre; }
.dj-doc pre.dj-code::before { content:attr(data-lang); position:absolute; top:0; right:0;
  background:""" + ACCENT + """; color:#fff; font-family:'Oswald',sans-serif; font-size:9.5px;
  font-weight:500; letter-spacing:1.2px; text-transform:uppercase; padding:2px 9px;
  border-radius:0 4px 0 4px; }
/* Pygments tokens, tuned to the dark code panel. */
.dj-doc .codehilite .k,.dj-doc .codehilite .kd,.dj-doc .codehilite .kn,
.dj-doc .codehilite .kr,.dj-doc .codehilite .kt { color:#ff8b90; font-weight:600; }
.dj-doc .codehilite .s,.dj-doc .codehilite .s1,.dj-doc .codehilite .s2,
.dj-doc .codehilite .sb,.dj-doc .codehilite .sd { color:#a8e6a3; }
.dj-doc .codehilite .c,.dj-doc .codehilite .c1,.dj-doc .codehilite .cm,
.dj-doc .codehilite .cp { color:#8b949e; font-style:italic; }
.dj-doc .codehilite .n,.dj-doc .codehilite .nv,.dj-doc .codehilite .nx { color:#e6e6e6; }
.dj-doc .codehilite .nf,.dj-doc .codehilite .nb { color:#9ecbff; }
.dj-doc .codehilite .m,.dj-doc .codehilite .mi,.dj-doc .codehilite .mf { color:#f0c987; }
.dj-doc .codehilite .o,.dj-doc .codehilite .p { color:#c9d1d9; }
.dj-doc .codehilite .na { color:#ffd7a0; }
.dj-doc pre.mermaid { background:#fff; border:1px solid """ + BORDER + """; color:""" + INK + """;
  text-align:center; }
.dj-doc hr { border:0; border-top:1px solid """ + BORDER + """; margin:1.4rem 26px; }
.dj-dfoot { display:flex; align-items:center; justify-content:space-between; gap:10px;
  flex-wrap:wrap; margin-top:20px; padding:12px 26px; border-top:1px solid """ + BORDER + """;
  color:""" + MUTED + """; font-family:'Oswald',sans-serif; font-size:10px;
  letter-spacing:1px; text-transform:uppercase; }
.dj-dfoot b { color:""" + INK + """; font-weight:600; }
"""

_FONT_IMPORT = ("@import url('https://fonts.googleapis.com/css2?"
                "family=Inter:wght@400;500;600;700&family=Oswald:wght@500;600;700&"
                "family=JetBrains+Mono:wght@400;500&display=swap');")

_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs"


def mermaid_frame(source: str, height: int = 460) -> str:
    """A self-contained HTML page that renders one Mermaid diagram.

    Used inside a Streamlit component frame, and reused by the download file.
    """
    src = _hh.escape(clean_mermaid(source))
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>"
        + _FONT_IMPORT +
        "html,body{margin:0;padding:0;background:#fff;"
        "font-family:'Inter',-apple-system,'Segoe UI',Arial,sans-serif;}"
        ".wrap{border:1px solid " + BORDER + ";border-radius:4px;padding:14px 10px;"
        "overflow:auto;}"
        ".mermaid{display:flex;justify-content:center;}"
        ".err{color:" + MUTED + ";font-size:12.5px;padding:10px 12px;}"
        ".err pre{background:" + PANEL + ";padding:10px;border-radius:3px;"
        "overflow:auto;font-size:11.5px;color:#333;}"
        "</style></head><body>"
        f'<div class="wrap"><div class="mermaid" id="d">{src}</div></div>'
        '<script type="module">'
        f'import mermaid from "{_MERMAID_CDN}";'
        'mermaid.initialize({startOnLoad:false,theme:"base",securityLevel:"strict",'
        'themeVariables:{fontFamily:"Inter, Segoe UI, Arial, sans-serif",'
        'fontSize:"13px",primaryColor:"#f5f5f5",primaryTextColor:"#141618",'
        'primaryBorderColor:"#141618",lineColor:"#ce242c",'
        'secondaryColor:"#fdeaeb",tertiaryColor:"#ffffff"}});'
        # A component frame is a fixed box, so a short diagram used to leave a
        # large blank gap under it. Streamlit's own resize protocol works from a
        # components.html iframe too, so the frame reports its real height once
        # the SVG exists and the gap disappears.
        # Measure the wrapper, not documentElement: scrollHeight includes the
        # frame's own viewport and over-reported by ~130px, which is exactly the
        # blank gap that appeared under short diagrams.
        'function fit(){try{var w=document.querySelector(".wrap");'
        'var h=Math.ceil(w?w.getBoundingClientRect().height:document.body.scrollHeight)+6;'
        'window.parent.postMessage({type:"streamlit:setFrameHeight",height:h},"*");'
        '}catch(e){}}'
        'const el=document.getElementById("d");const src=el.textContent;'
        'mermaid.render("g0",src).then(function(r){el.innerHTML=r.svg;'
        'fit();setTimeout(fit,120);setTimeout(fit,400);})'
        '.catch(function(e){setTimeout(fit,60);el.parentElement.parentElement.innerHTML='
        '"<div class=\'err\'>This diagram could not be drawn. '
        'Use <b>Regenerate</b>, or copy the source below into mermaid.live:"'
        '+"<pre>"+src.replace(/[<>&]/g,function(c){return {"<":"&lt;",">":"&gt;",'
        '"&":"&amp;"}[c];})+"</pre></div>";});'
        "</script></body></html>"
    )


def download_html(md: str, heading: str, logo_uri: str = "", meta: dict = None,
                  auto_print: bool = False, eyebrow: str = "DrJhaGPT Pro") -> str:
    """A self-contained HTML document - opens in Word, or prints to PDF.

    Any Mermaid diagram is rendered live here too, so the saved file and the
    printed page look the same as the app.
    """
    body = to_document(md, logo_uri, meta, eyebrow)
    has_mermaid = 'class="mermaid"' in body
    mermaid_js = (
        '<script type="module">'
        f'import mermaid from "{_MERMAID_CDN}";'
        'mermaid.initialize({startOnLoad:true,theme:"base",securityLevel:"strict",'
        'themeVariables:{fontFamily:"Inter, Segoe UI, Arial, sans-serif",'
        'fontSize:"13px",primaryColor:"#f5f5f5",primaryTextColor:"#141618",'
        'primaryBorderColor:"#141618",lineColor:"#ce242c"}});'
        "</script>") if has_mermaid else ""
    autoprint = ("<script>window.addEventListener('load',function(){"
                 "setTimeout(function(){window.print();},900);});</script>"
                 ) if auto_print else ""
    try:
        import pygments  # noqa: F401
        pyg = ""            # token colours already live in DOC_CSS
    except ImportError:
        pyg = ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_hh.escape(heading)} · DrJhaGPT Pro</title>"
        "<style>" + _FONT_IMPORT +
        "body{background:#f0f0f0;margin:0;padding:26px 14px;"
        "font-family:'Inter','Segoe UI',Arial,sans-serif;}"
        ".page{max-width:860px;margin:0 auto;}"
        + DOC_CSS + pyg +
        "@media print{body{background:#fff;padding:0;}"
        ".dj-doc{border:0;box-shadow:none;border-radius:0;}"
        ".dj-doc pre{page-break-inside:avoid;}"
        ".dj-doc h2,.dj-doc h3{page-break-after:avoid;}}"
        "</style></head><body><div class='page'>"
        f"{body}</div>{mermaid_js}{autoprint}</body></html>"
    )
