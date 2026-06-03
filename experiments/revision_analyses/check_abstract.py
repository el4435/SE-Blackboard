"""Count words in the revised abstract."""
import re
with open(r"E:\SE-Blackboard\paper\ACCESS_latex_template_20240429\main.tex",
          encoding="utf-8") as f:
    src = f.read()

m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", src, re.S)
text = m.group(1)
# strip LaTeX wrapping commands but preserve their inner text
for cmd in ("textbf", "emph", "textit", "texttt"):
    text = re.sub(r"\\" + cmd + r"\{([^}]*)\}", r"\1", text)
# remove $...$ math
text = re.sub(r"\$[^$]*\$", "X", text)
# remove other backslash commands
text = re.sub(r"\\[A-Za-z]+", "", text)
# remove punctuation that is not a separator
text = re.sub(r"[{}\\~]", " ", text)
text = re.sub(r"\s+", " ", text).strip()
words = [w for w in text.split() if any(c.isalpha() or c.isdigit() for c in w)]
print(f"Abstract word count: {len(words)} (IEEE Access limit: 150-250)")
print()
print(text)
