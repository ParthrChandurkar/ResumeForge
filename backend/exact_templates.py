import re


def latex_escape(value: object) -> str:
    """Escape model-authored prose without touching template commands."""
    text = str(value or "")
    for old, new in [
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
        ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        text = text.replace(old, new)
    return text


def exact_source_path(user_id: str, template_id: str) -> str:
    """Return the private companion TEX path for an uploaded template."""
    return f"users/{user_id}/templates/{template_id}/source.tex"


def _section(source: str, start_marker: str, end_marker: str) -> tuple[int, int, str] | None:
    start = source.find(start_marker)
    end = source.find(end_marker, start + len(start_marker))
    return (start, end, source[start:end]) if start >= 0 and end >= 0 else None


def _replace_command_arguments(block: str, command: str, values: list[object]) -> str:
    """Replace balanced single arguments in order while retaining all surrounding TEX."""
    needle = f"\\{command}{{"
    cursor = 0
    replacements = iter(values)
    output = []
    while True:
        start = block.find(needle, cursor)
        if start < 0:
            output.append(block[cursor:])
            break
        output.append(block[cursor:start + len(needle)])
        depth, index = 1, start + len(needle)
        while index < len(block) and depth:
            if block[index] == "{" and (index == 0 or block[index - 1] != "\\"):
                depth += 1
            elif block[index] == "}" and (index == 0 or block[index - 1] != "\\"):
                depth -= 1
            index += 1
        original = block[start + len(needle):index - 1]
        replacement = next(replacements, None)
        output.append(original if replacement is None else latex_escape(replacement))
        output.append("}")
        cursor = index
    return "".join(output)


def render_cloud_resume(source: str, resume: dict) -> str:
    """Fill only prose slots in the original cloud TEX; commands and links remain byte-stable."""
    rendered = source
    profile = latex_escape(resume.get("profile", ""))
    rendered = re.sub(
        r"(%-----------SUMMARY-----------\s*\\section\{Summary\}\s*\\small\{).*?(\}\s*\\vspace\{-1pt\})",
        lambda match: match.group(1) + profile + match.group(2), rendered, count=1, flags=re.DOTALL,
    )

    skills = resume.get("skill_groups", [])[:4]
    if skills:
        skill_lines = "\n".join(
            rf"\textbf{{{latex_escape(group.get('label', '')).rstrip(':')}:}} {latex_escape(group.get('items', ''))} \\"
            for group in skills
        )
        rendered = re.sub(
            r"(\\section\{Skills\}\s*).*?(\s*\\vspace\{-8pt\})",
            lambda match: match.group(1) + skill_lines + match.group(2), rendered, count=1, flags=re.DOTALL,
        )

    experience = _section(rendered, "%-----------EXPERIENCE-----------", "%-----------PROJECTS-----------")
    if experience:
        start, end, block = experience
        bullets = [bullet for entry in resume.get("experiences", []) for bullet in entry.get("bullets", [])]
        rendered = rendered[:start] + _replace_command_arguments(block, "resumeItem", bullets) + rendered[end:]

    projects = _section(rendered, "%-----------PROJECTS-----------", "%-----------EDUCATION-----------")
    if projects:
        start, end, block = projects
        bullets = [bullet for entry in resume.get("secondary_entries", []) for bullet in entry.get("bullets", [])]
        rendered = rendered[:start] + _replace_command_arguments(block, "resumeItem", bullets) + rendered[end:]

    education = _section(rendered, "%-----------EDUCATION-----------", "%-----------CERTIFICATIONS-----------")
    if education and resume.get("education_coursework"):
        start, end, block = education
        coursework = f"Relevant Coursework: {resume['education_coursework']}"
        rendered = rendered[:start] + _replace_command_arguments(block, "resumeItem", [coursework]) + rendered[end:]
    return rendered


def render_cover_letter(source: str, letter: dict, contact: dict) -> str:
    """Fill the original cover-letter body while preserving its exact preamble and spacing recipe."""
    today_index = source.find(r"\today")
    end_index = source.rfind(r"\end{document}")
    if today_index < 0 or end_index < 0:
        return source
    prefix = source[:today_index] + r"\today"
    subject = re.sub(r"^(?:\s*re\s*:\s*)+", "", str(letter.get("subject") or ""), flags=re.IGNORECASE).strip()
    evidence = list(letter.get("evidence_sections", []))[:3]
    while len(evidence) < 3:
        evidence.append({"heading": "", "body": ""})
    body = rf"""

\vspace{{10pt}}

{latex_escape(letter.get('recipient_team'))} \\
{latex_escape(letter.get('company'))} \\
{latex_escape(letter.get('location'))}

\vspace{{10pt}}

\textbf{{Re: {latex_escape(subject)}}}

\vspace{{10pt}}

{latex_escape(letter.get('salutation'))}

\vspace{{6pt}}

{latex_escape(letter.get('opening'))}

\vspace{{8pt}}

\textbf{{{latex_escape(evidence[0].get('heading'))}}}

{latex_escape(evidence[0].get('body'))}

\vspace{{8pt}}

\textbf{{{latex_escape(evidence[1].get('heading'))}}}

{latex_escape(evidence[1].get('body'))}

\vspace{{8pt}}

\textbf{{{latex_escape(evidence[2].get('heading'))}}}

{latex_escape(evidence[2].get('body'))}

\vspace{{8pt}}

{latex_escape(letter.get('motivation'))}

\vspace{{8pt}}

{latex_escape(letter.get('closing'))}

\vspace{{16pt}}

Yours sincerely,

\vspace{{20pt}}

\textbf{{{latex_escape(contact.get('name') or 'Candidate')}}}

\end{{document}}
"""
    return prefix + body
