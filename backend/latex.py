from datetime import date
import re


def esc(value: object) -> str:
    """Escape user and model text for safe LaTeX output."""
    text = str(value or "")
    for old, new in [
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
        ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"), ("—", "---"), ("–", "--"),
    ]:
        text = text.replace(old, new)
    return text


def linked_entry(value: object, raw_url: object = "") -> str:
    """Render an entry subtitle with its original embedded link when available."""
    text = str(value or "")
    url = safe_url(raw_url)
    if not url:
        return esc(text)
    index = text.lower().find("ieee")
    if index < 0:
        return rf"\href{{{url}}}{{{esc(text)}}}"
    return esc(text[:index]) + rf"\href{{{url}}}{{{esc(text[index:])}}}"


def certification_tex(item: object, consulting: bool) -> str:
    """Attach the original certificate target to a generated certification name."""
    if isinstance(item, dict):
        text = item.get("name", "")
        issuer = item.get("issuer", "")
        if issuer:
            text = f"{text} – {issuer}"
        supplied_url = safe_url(item.get("url", ""))
    else:
        text = str(item or "")
        supplied_url = ""
    clean = text.replace("View Certificate", "").replace("Verify", "").strip(" –-")
    if supplied_url:
        label = "Verify" if consulting else "View Certificate"
        return esc(clean) + rf" \hfill \href{{{supplied_url}}}{{{label}}}"
    return esc(clean)


def safe_url(value: object) -> str:
    """Keep only link schemes supported in generated LaTeX documents."""
    url = str(value or "").strip()
    return url if url.startswith(("https://", "http://", "mailto:", "tel:")) else ""


def contact_tex(contact: dict, include_github: bool = True, full_labels: bool = False) -> str:
    """Render only available user contact fields as clickable LaTeX links."""
    fields = []
    phone = str(contact.get("phone", "")).strip()
    email = str(contact.get("email", "")).strip()
    if phone:
        fields.append(rf"\href{{tel:{''.join(ch for ch in phone if ch.isdigit() or ch == '+')}}}{{{esc(phone)}}}")
    if email:
        fields.append(rf"\href{{mailto:{email}}}{{{esc(email)}}}")
    for key, label in (("github", "GitHub"), ("linkedin", "LinkedIn"), ("portfolio", "Portfolio")):
        if key == "github" and not include_github:
            continue
        url = safe_url(contact.get(key, ""))
        if url:
            display = url.removeprefix("https://").removeprefix("http://").rstrip("/") if full_labels else label
            fields.append(rf"\href{{{url}}}{{{esc(display)}}}")
    return r" $\cdot$ ".join(fields)


def bullet_tex(value: object, emphasize_metrics: bool = False) -> str:
    """Escape a bullet while retaining the consulting template's bold metrics."""
    text = str(value or "")
    if not emphasize_metrics:
        return esc(text)
    parts = re.split(r"(\b\d+(?:\.\d+)?%)", text)
    return "".join(rf"\textbf{{{esc(part)}}}" if re.fullmatch(r"\d+(?:\.\d+)?%", part) else esc(part) for part in parts)


PREAMBLE = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.38in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,enumitem,hyperref,xcolor,tabularx}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\definecolor{ruleblue}{HTML}{5D6E9B}
\hypersetup{colorlinks=true,urlcolor=blue}
\newcommand{\sectionline}[1]{\vspace{3pt}{\Large\bfseries #1}\vspace{1pt}\\[-4pt]\color{ruleblue}\rule{\linewidth}{0.45pt}\color{black}\vspace{2pt}}
\newcommand{\entry}[4]{\textbf{#1}\hfill\textbf{#3}\\\textit{#2}\hfill\textit{#4}}
\setlist[itemize]{leftmargin=12pt,itemsep=0pt,topsep=1pt,parsep=0pt}
\begin{document}
"""

PRECISION_PREAMBLE = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.39in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{enumitem,hyperref,xcolor,tabularx}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\definecolor{sectionblue}{HTML}{0A2463}
\hypersetup{colorlinks=true,urlcolor=blue}
\newcommand{\sectionline}[1]{\vspace{3pt}{\fontsize{12}{13}\selectfont #1}\vspace{1pt}\\[-4pt]\color{black}\rule{\linewidth}{0.4pt}\color{black}\vspace{2pt}}
\newcommand{\entry}[4]{\textbf{#1}\hfill\textbf{#3}\\\textit{#2}\hfill\textit{#4}}
\setlist[itemize]{leftmargin=11pt,itemsep=0pt,topsep=1pt,parsep=0pt}
\begin{document}\fontsize{9}{10.2}\selectfont
"""


def resume_tex(run: dict) -> str:
    """Render a tailored resume as an Overleaf-ready LaTeX document."""
    resume = run["resume"]
    consulting = run.get("template_track") == "consulting"
    precision = run.get("layout_profile") == "precision"
    rule = "ruleblue" if consulting else "black"
    if precision:
        preamble = PRECISION_PREAMBLE
        if consulting:
            preamble = preamble.replace(r"\color{black}\rule", r"\color{sectionblue}\rule")
        parts = [preamble]
    else:
        parts = [PREAMBLE.replace("\\color{ruleblue}\\rule", f"\\color{{{rule}}}\\rule")]
    contact_data = resume.get("contact", {})
    name = contact_data.get("name") or "Candidate"
    name_size = "24.8}{25" if precision else "22}{24"
    parts.append(r"\begin{center}{\fontsize{" + name_size + r"}\selectfont\scshape " + esc(name) + r"}\\[-1pt]")
    parts.append(r"{\large\bfseries " + esc(resume.get("headline")) + r"}\\[2pt]")
    parts.append(contact_tex(contact_data, include_github=not consulting, full_labels=precision) + r"\end{center}")
    parts.append("\\sectionline{" + esc(resume.get("profile_title", "Profile")) + "}\n" + esc(resume.get("profile")))
    parts.append("\\sectionline{" + esc(resume.get("skills_title", "Skills")) + "}")
    competency_bullets = resume.get("competency_bullets", [])
    if precision and consulting and competency_bullets:
        rows = [competency_bullets[index:index + 3] for index in range(0, len(competency_bullets), 3)]
        row_separator = r" \\" + "\n"
        parts.append(r"\begin{tabularx}{\linewidth}{@{}XXX@{}}" + row_separator.join(" & ".join(r"$\bullet$ " + esc(item) for item in row) for row in rows) + r"\end{tabularx}")
    for group in resume.get("skill_groups", []):
        parts.append("\\textbf{" + esc(group.get("label")) + ":} " + esc(group.get("items")) + r"\\")
    parts.append("\\sectionline{" + esc(resume.get("experience_title", "Experience")) + "}")
    for entry in resume.get("experiences", []):
        parts.append("\\entry{" + esc(entry.get("title")) + "}{" + linked_entry(entry.get("subtitle"), entry.get("url")) + "}{" + esc(entry.get("date")) + "}{" + esc(entry.get("location")) + "}")
        if entry.get("technologies"):
            parts.append(r"\\[-1pt]\textit{" + esc(entry.get("technologies")) + "}")
        parts.append(r"\begin{itemize}" + "".join("\\item " + bullet_tex(b, precision and consulting) for b in entry.get("bullets", [])) + r"\end{itemize}")
    if resume.get("secondary_entries"):
        parts.append("\\sectionline{" + esc(resume.get("secondary_title", "Projects")) + "}")
        for entry in resume.get("secondary_entries", []):
            parts.append("\\entry{" + esc(entry.get("title")) + "}{" + linked_entry(entry.get("subtitle"), entry.get("url")) + "}{" + esc(entry.get("date")) + "}{" + esc(entry.get("location")) + "}")
            if entry.get("technologies"):
                parts.append(r"\\[-1pt]\textit{" + esc(entry.get("technologies")) + "}")
            parts.append(r"\begin{itemize}" + "".join("\\item " + bullet_tex(b, precision and consulting) for b in entry.get("bullets", [])) + r"\end{itemize}")
    parts.append(r"\sectionline{Education}\textbf{" + esc(resume.get("education_institution")) + r"}\hfill\textbf{" + esc(resume.get("education_dates")) + r"}\\\textit{" + esc(resume.get("education_degree")) + r"}\hfill\textit{" + esc(resume.get("education_grade")) + r"}\\[-1pt]Relevant Coursework: " + esc(resume.get("education_coursework")))
    parts.append(r"\sectionline{Certifications \& Professional Development}\begin{itemize}")
    parts.extend("\\item " + certification_tex(item, consulting) for item in resume.get("certifications", []))
    parts.append(r"\end{itemize}\end{document}")
    return "\n".join(parts)


def cover_letter_tex(run: dict) -> str:
    """Render a tailored cover letter as an Overleaf-ready LaTeX document."""
    letter = run["cover_letter"]
    display_date = date.today().strftime("%B %d, %Y").replace(" 0", " ")
    contact = letter.get("contact") or run.get("resume", {}).get("contact", {})
    name = contact.get("name") or "Candidate"
    parts = [r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=0.55in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,hyperref}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{9pt}
\begin{document}
""" + r"{\LARGE\bfseries " + esc(name) + r"}\\[3pt]" + "\n" + contact_tex(contact)]
    parts.append(esc(display_date) + r"\\[8pt]")
    parts.append(esc(letter.get("recipient_team")) + r"\\" + esc(letter.get("company")) + r"\\" + esc(letter.get("location")))
    subject = re.sub(r"^(?:\s*re\s*:\s*)+", "", str(letter.get("subject") or ""), flags=re.IGNORECASE).strip()
    parts.append(r"\textbf{Re: " + esc(subject) + "}")
    parts.append(esc(letter.get("salutation")))
    parts.append(esc(letter.get("opening")))
    for section in letter.get("evidence_sections", []):
        parts.append(r"\textbf{" + esc(section.get("heading")) + "}\n\n" + esc(section.get("body")))
    parts.append(esc(letter.get("motivation")))
    parts.append(esc(letter.get("closing")))
    parts.append(r"Yours sincerely,\\[14pt]\textbf{" + esc(name) + r"}\end{document}")
    return "\n\n".join(parts)
