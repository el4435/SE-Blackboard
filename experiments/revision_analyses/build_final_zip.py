"""Build the IEEE Access final-files submission zip.

Bundles the manuscript source, compiled PDF, Graphical Abstract, GA caption,
Response to Reviewers, the IEEE Access template (.cls/.bst/.sty/fonts),
all figures, and author photos. Excludes backups, aux files, and unrelated
content.
"""

from __future__ import annotations

import os
import zipfile

ROOT = r"E:\SE-Blackboard\paper"
TEX_DIR = os.path.join(ROOT, "ACCESS_latex_template_20240429")
DST = os.path.join(ROOT, "SE_Blackboard_FINAL.zip")


# Files in paper/ root to include
ROOT_FILES = [
    "FINAL Article.pdf",
    "GA.jpg",
    "GA_caption.docx",
    "Response_to_Reviewers.md",
    "Response_to_Reviewers.docx",
]

# Files in the LaTeX template directory to include verbatim. Anything not
# listed here (main.pdf intermediate, .aux, .log, .bbl, *_original.tex,
# access.pdf left over, .synctex, etc.) is excluded.
TEX_KEEP_EXACT = {
    "main.tex",
    "references.bib",
    "ieeeaccess.cls",
    "IEEEtran.cls",
    "IEEEtran.bst",
    "spotcolor.sty",
    "author_liu.jpg",
    "author_zhu.png",
    "author_dong.jpg",
    "equation3.png",
    "fig1.png",
    "bullet.png",
    "logo.png",
    "notaglinelogo.png",
}

# All font files matching these extensions are template assets and should
# travel with the source for clean production-side recompilation.
TEX_KEEP_FONT_EXTS = (".pfb", ".tfm", ".fd", ".map")

# Subdirectories inside the template dir to include
TEX_KEEP_SUBDIRS = ("figures",)


def main() -> None:
    if os.path.exists(DST):
        os.remove(DST)

    written: list[tuple[str, str, int]] = []  # (src, arcname, size)

    with zipfile.ZipFile(DST, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Top-level deliverables
        for name in ROOT_FILES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                print(f"  MISSING (skipped): {src}")
                continue
            zf.write(src, arcname=name)
            written.append((src, name, os.path.getsize(src)))

        # 2. Manuscript files at the root of the zip (production prefers flat)
        for name in sorted(os.listdir(TEX_DIR)):
            src = os.path.join(TEX_DIR, name)
            if os.path.isfile(src):
                ext = os.path.splitext(name)[1].lower()
                if name in TEX_KEEP_EXACT or ext in TEX_KEEP_FONT_EXTS:
                    zf.write(src, arcname=name)
                    written.append((src, name, os.path.getsize(src)))
            elif os.path.isdir(src) and name in TEX_KEEP_SUBDIRS:
                for fn in sorted(os.listdir(src)):
                    fpath = os.path.join(src, fn)
                    if os.path.isfile(fpath):
                        arc = f"{name}/{fn}"
                        zf.write(fpath, arcname=arc)
                        written.append((fpath, arc, os.path.getsize(fpath)))

    total = sum(s for _, _, s in written)
    print(f"Wrote {DST}")
    print(f"Total entries: {len(written)}, total uncompressed: {total:,} bytes")
    print(f"Final zip size: {os.path.getsize(DST):,} bytes")
    print()
    print("Manifest:")
    for _, arc, size in sorted(written, key=lambda x: x[1].lower()):
        print(f"  {arc:<60s} {size:>10,} B")


if __name__ == "__main__":
    main()
