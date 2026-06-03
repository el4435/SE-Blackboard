#!/usr/bin/env python3
"""Convert paper_final.md to IEEE Access LaTeX format (main.tex)."""

import re
import shutil
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).parent
MD_FILE = BASE_DIR / "paper_final.md"
TEMPLATE_DIR = BASE_DIR / "ACCESS_latex_template_20240429"
OUTPUT_FILE = TEMPLATE_DIR / "main.tex"
BIB_SRC = BASE_DIR / "references.bib"
BIB_DST = TEMPLATE_DIR / "references.bib"

# --- Preamble (from access.tex) ---
PREAMBLE = r"""\documentclass{ieeeaccess}
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}

\usepackage{bm}
\makeatletter
\AtBeginDocument{\DeclareMathVersion{bold}
\SetSymbolFont{operators}{bold}{T1}{times}{b}{n}
\SetSymbolFont{NewLetters}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathrm}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathit}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathbf}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathtt}{bold}{OT1}{pcr}{b}{n}
\SetSymbolFont{symbols}{bold}{OMS}{cmsy}{b}{n}
\renewcommand\boldmath{\@nomath\boldmath\mathversion{bold}}}
\makeatother

\def\BibTeX{{\rm B\kern-.05em{\sc i\kern-.025em b}\kern-.08em
    T\kern-.1667em\lower.7ex\hbox{E}\kern-.125emX}}

\begin{document}
\history{Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.}
\doi{10.1109/ACCESS.2024.0429000}

"""

TITLE = "SE-Blackboard: A Shared-State Architecture for Multi-Agent Software Engineering Pipelines"

AUTHOR_BLOCK = r"""\author{\uppercase{First A. Author}\authorrefmark{1},
\uppercase{Second B. Author}\authorrefmark{2}}

\address[1]{Department, University, City, Country (e-mail: author1@example.com)}
\address[2]{Department, University, City, Country (e-mail: author2@example.com)}

\markboth
{Author \headeretal: SE-Blackboard: A Shared-State Architecture for Multi-Agent SE Pipelines}
{Author \headeretal: SE-Blackboard: A Shared-State Architecture for Multi-Agent SE Pipelines}

\corresp{Corresponding author: First A. Author (e-mail: author1@example.com).}
"""

KEYWORDS = (
    "multi-agent systems, large language models, software engineering, "
    "blackboard architecture, shared state, communication architecture, "
    "information fidelity, SWE-bench"
)


def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_yaml_front_matter(text: str) -> str:
    """Remove YAML front matter between --- delimiters."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip("\n")
    return text


def extract_abstract(text: str) -> tuple[str, str]:
    """Extract abstract (lines starting with >) and return (abstract, remaining)."""
    lines = text.split("\n")
    abstract_lines = []
    remaining_lines = []
    in_abstract_section = False
    abstract_done = False

    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip the "## Abstract" heading
        if re.match(r"^##\s+Abstract\s*$", line):
            in_abstract_section = True
            i += 1
            continue
        if in_abstract_section and not abstract_done:
            if line.startswith(">"):
                # Strip the > prefix
                content = line[1:].strip()
                if content:
                    abstract_lines.append(content)
                else:
                    # Empty > line = paragraph separator within abstract
                    abstract_lines.append("")
                i += 1
                continue
            elif line.strip() == "" and not abstract_lines:
                # Skip blank lines before abstract content
                i += 1
                continue
            else:
                abstract_done = True
                remaining_lines.append(line)
                i += 1
                continue
        remaining_lines.append(line)
        i += 1

    abstract_text = "\n".join(abstract_lines)
    remaining_text = "\n".join(remaining_lines)
    return abstract_text, remaining_text


def convert_citations(text: str) -> str:
    r"""Convert Markdown citations to LaTeX \cite{} commands."""
    # Multi-key citations: [@key1; @key2] -> \cite{key1, key2}
    def multi_cite(m):
        keys = re.findall(r"@([\w-]+)", m.group(0))
        return r"\cite{" + ", ".join(keys) + "}"
    text = re.sub(r"\[(?:@[\w-]+(?:;\s*)?)+\]", multi_cite, text)

    # Text citations at start of sentence: @key provide/show/examine/further/explore/describe
    # These are "Author et al." style
    text_cite_map = {
        "he2025llm": "He et al.",
        "zhang2025why": "Zhang et al.",
        "park2023generative": "Park et al.",
        "nii1986blackboard": "Nii",
        "wang2025lbmas": "Wang et al.",
        "salemi2025llm": "Salemi et al.",
    }
    for key, author in text_cite_map.items():
        # Match @key at word boundary (not inside brackets)
        pattern = r"(?<!\[)@" + re.escape(key)
        replacement = author + "~\\\\cite{" + key + "}"
        text = re.sub(pattern, replacement, text)
    # Clean up double-escaped cite from text citations
    text = text.replace("\\\\cite{", "\\cite{")

    return text


def convert_display_math(text: str) -> str:
    """Convert $$...$$ to \\[...\\] (unnumbered display math)."""
    # Handle multi-line $$...$$ blocks
    def replace_display(m):
        content = m.group(1).strip()
        return r"\[" + content + r"\]"
    text = re.sub(r"\$\$(.*?)\$\$", replace_display, text, flags=re.DOTALL)
    return text


def is_latex_structure_line(line: str) -> bool:
    """Check if a line is a LaTeX structural command (not regular text with citations)."""
    stripped = line.strip()
    latex_patterns = [
        r"^\\begin\{", r"^\\end\{", r"^\\caption", r"^\\label",
        r"^\\centering", r"^\\includegraphics", r"^\\hline",
        r"^\\PARstart",
        r"&.*\\\\$",  # table row
        r"^\\multicolumn",
    ]
    for pat in latex_patterns:
        if re.search(pat, stripped):
            return True
    return False


def convert_bold_italic(line: str) -> str:
    """Convert **text** to \\textbf{text} and *text* to \\emph{text}."""
    # Bold first (** before *)
    line = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", line)
    # Italic
    line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", line)
    return line


def convert_sections(text: str) -> str:
    """Convert Markdown headings to LaTeX section commands."""
    lines = text.split("\n")
    result = []
    for line in lines:
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            result.append(r"\subsubsection{" + m.group(1).rstrip(".") + "}")
            continue
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            result.append(r"\subsection{" + m.group(1) + "}")
            continue
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            title = m.group(1)
            if title.strip() == "References":
                continue  # Skip, handled by bibliography
            if title.strip() == "Acknowledgement":
                result.append(r"\section*{Acknowledgment}")
                continue
            result.append(r"\section{" + title + "}")
            continue
        result.append(line)
    return "\n".join(result)


def convert_numbered_lists(text: str) -> str:
    """Convert Markdown numbered lists to LaTeX enumerate."""
    lines = text.split("\n")
    result = []
    in_list = False

    for line in lines:
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            if not in_list:
                result.append(r"\begin{enumerate}")
                in_list = True
            item_text = m.group(2)
            result.append(r"\item " + item_text)
        else:
            if in_list:
                # Check if this is a continuation of the previous item (indented)
                if line.startswith("    ") or line.startswith("\t"):
                    # Continuation of previous item
                    result[-1] += " " + line.strip()
                    continue
                if line.strip() == "":
                    # Could be spacing within list; peek ahead not trivial,
                    # so just keep going
                    result.append("")
                    continue
                # End of list
                result.append(r"\end{enumerate}")
                in_list = False
            result.append(line)

    if in_list:
        result.append(r"\end{enumerate}")

    return "\n".join(result)


def fix_image_paths(text: str) -> str:
    """Convert ../figures/ to ../../figures/ for template directory."""
    return text.replace("../figures/", "../../figures/")


def escape_percent_in_text(text: str) -> str:
    """Escape bare % in text lines (not already escaped)."""
    lines = text.split("\n")
    env_depth = 0
    result = []
    for line in lines:
        begins = len(re.findall(r"\\begin\{(table|figure|tabular)", line))
        ends = len(re.findall(r"\\end\{(table|figure|tabular)", line))
        env_depth += begins - ends

        if "%" in line and env_depth <= 0 and not is_latex_structure_line(line):
            # Escape unescaped % (not preceded by \)
            line = re.sub(r"(?<!\\)%", r"\\%", line)
        result.append(line)

        if env_depth < 0:
            env_depth = 0
    return "\n".join(result)


def add_parstart(text: str) -> str:
    """Add \\PARstart to the first paragraph of Introduction."""
    # Find the \section{Introduction} and modify the next non-empty paragraph
    lines = text.split("\n")
    result = []
    found_intro = False
    parstart_done = False

    for i, line in enumerate(lines):
        if r"\section{Introduction}" in line:
            found_intro = True
            result.append(line)
            continue
        if found_intro and not parstart_done:
            if line.strip() == "":
                result.append(line)
                continue
            # This is the first paragraph line after Introduction
            # Find first word and apply \PARstart
            m = re.match(r"^(\w)(\w+)\b(.*)$", line)
            if m:
                line = r"\PARstart{" + m.group(1) + "}{" + m.group(2) + "}" + m.group(3)
            parstart_done = True
            result.append(line)
            continue
        result.append(line)

    return "\n".join(result)


def clean_empty_lines(text: str) -> str:
    """Remove excessive blank lines (max 2 consecutive)."""
    return re.sub(r"\n{4,}", "\n\n\n", text)


def remove_trailing_references_section(text: str) -> str:
    """Remove any leftover # References heading."""
    text = re.sub(r"\\section\{References\}\s*", "", text)
    return text


def process_inline_formatting_all_lines(text: str) -> str:
    """Apply bold/italic conversion line by line, skipping LaTeX envs."""
    lines = text.split("\n")
    env_depth = 0
    result = []

    for line in lines:
        # Track LaTeX environment depth (table, figure, etc.)
        begins = len(re.findall(r"\\begin\{(table|figure|tabular)", line))
        ends = len(re.findall(r"\\end\{(table|figure|tabular)", line))
        env_depth += begins - ends

        if env_depth > 0 or begins > 0 or is_latex_structure_line(line):
            result.append(line)
        else:
            result.append(convert_bold_italic(line))

        if env_depth < 0:
            env_depth = 0

    return "\n".join(result)


def convert_md_to_tex():
    """Main conversion function."""
    md_text = read_md(MD_FILE)

    # Step 1: Strip YAML front matter
    md_text = strip_yaml_front_matter(md_text)

    # Step 2: Extract abstract
    abstract_text, body_text = extract_abstract(md_text)

    # Step 3: Convert citations (before other transformations)
    abstract_text = convert_citations(abstract_text)
    body_text = convert_citations(body_text)

    # Step 3b: Convert bold/italic in abstract
    abstract_lines = abstract_text.split("\n")
    abstract_text = "\n".join(convert_bold_italic(l) for l in abstract_lines)

    # Step 4: Convert display math
    body_text = convert_display_math(body_text)

    # Step 5: Fix image paths
    body_text = fix_image_paths(body_text)

    # Step 6: Convert sections
    body_text = convert_sections(body_text)

    # Step 7: Convert numbered lists
    body_text = convert_numbered_lists(body_text)

    # Step 8: Apply bold/italic formatting (outside LaTeX envs)
    body_text = process_inline_formatting_all_lines(body_text)

    # Step 9: Add \PARstart to Introduction
    body_text = add_parstart(body_text)

    # Step 10: Escape percent signs in text
    body_text = escape_percent_in_text(body_text)

    # Step 11: Remove trailing References section
    body_text = remove_trailing_references_section(body_text)

    # Step 12: Clean excessive blank lines
    body_text = clean_empty_lines(body_text)

    # --- Assemble the document ---
    tex = PREAMBLE
    tex += r"\title{" + TITLE + "}\n"
    tex += AUTHOR_BLOCK + "\n"

    # Abstract
    tex += r"\begin{abstract}" + "\n"
    tex += abstract_text + "\n"
    tex += r"\end{abstract}" + "\n\n"

    # Keywords
    tex += r"\begin{keywords}" + "\n"
    tex += KEYWORDS + "\n"
    tex += r"\end{keywords}" + "\n\n"

    tex += r"\titlepgskip=-21pt" + "\n\n"
    tex += r"\maketitle" + "\n\n"

    # Body
    tex += body_text.strip() + "\n\n"

    # Bibliography
    tex += r"\bibliographystyle{IEEEtran}" + "\n"
    tex += r"\bibliography{references}" + "\n\n"

    # End
    tex += r"\EOD" + "\n\n"
    tex += r"\end{document}" + "\n"

    return tex


def main():
    # Copy references.bib
    shutil.copy2(BIB_SRC, BIB_DST)
    print(f"Copied {BIB_SRC} -> {BIB_DST}")

    # Generate main.tex
    tex_content = convert_md_to_tex()
    OUTPUT_FILE.write_text(tex_content, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")

    # Verification stats
    tables = len(re.findall(r"\\begin\{table", tex_content))
    figures = len(re.findall(r"\\begin\{figure", tex_content))
    cites = len(re.findall(r"\\cite\{", tex_content))
    sections = len(re.findall(r"\\section\{", tex_content))
    subsections = len(re.findall(r"\\subsection\{", tex_content))
    subsubsections = len(re.findall(r"\\subsubsection\{", tex_content))

    print(f"\nVerification:")
    print(f"  Tables:         {tables}")
    print(f"  Figures:        {figures}")
    print(f"  \\cite{{}} calls: {cites}")
    print(f"  Sections:       {sections}")
    print(f"  Subsections:    {subsections}")
    print(f"  Subsubsections: {subsubsections}")


if __name__ == "__main__":
    main()
