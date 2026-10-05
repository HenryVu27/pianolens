"""Render the three R-11 annotated-score PDFs to PNG, with a positioned text dump per page.

Encoding aid only (see data/interim/tonebase_annotations/PROTOCOL.md). Output must go to an
untracked folder (scratchpad or data/interim/); the PDFs are licence-unclear (BL-29).

    uv run --no-project --with pymupdf python render_pages.py OUT_DIR
    uv run --no-project --with pymupdf python render_pages.py OUT_DIR --crop TAG PAGE X0 Y0 X1 Y1

Pages are rendered 1800 px wide; text boxes and crop coordinates use that pixel space.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "tonebase"
PDFS = {
    "NOC": "pdf/Romantic/Chopin Nocturne in E-flat Major Op. 9 No. 2/"
           "chopin_-_nocturne_in_e-flat_major_op._9_no._2_-_claire_huangci_-_tonebase_annotated_edition.pdf",
    "WAL": "pdf/Romantic/Chopin Waltz in D-flat Op. 64 No. 1/"
           "chopin_-_minute_waltz_in_d-flat_op._64_no._1_-_benjamin_laude_-_tonebase_annotated_edition.pdf",
    "ETU": "pdf/Technical Approaches/Chopin Étude Training/"
           "chopin_-_etude_op_10_no_4_-_marina_lomazov_-_tonebase_piano_annotated_edition.pdf",
}  # fmt: skip
WIDTH = 1800


def render(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for tag, rel in PDFS.items():
        doc = pymupdf.open(ROOT / rel)
        for i, page in enumerate(doc):
            z = WIDTH / page.rect.width
            page.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(out / f"{tag}_p{i}.png")
            lines = [f"page {i} of {doc.page_count}; boxes in {WIDTH}-px PNG space"]
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if text:
                        x0, y0, x1, y1 = (v * z for v in line["bbox"])
                        lines.append(f"[{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}] {text}")
            (out / f"{tag}_p{i}_text.txt").write_text("\n".join(lines) + "\n")
        print(tag, doc.page_count, "pages")


def crop(out: Path, tag: str, page_no: int, box: list[float]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    page = pymupdf.open(ROOT / PDFS[tag])[page_no]
    z = WIDTH / page.rect.width
    clip = pymupdf.Rect(*(v / z for v in box))
    s = 1600 / clip.width
    path = out / f"{tag}_p{page_no}_crop_{'_'.join(str(int(v)) for v in box)}.png"
    page.get_pixmap(matrix=pymupdf.Matrix(s, s), clip=clip).save(path)
    print(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--crop", nargs=6, metavar=("TAG", "PAGE", "X0", "Y0", "X1", "Y1"))
    a = ap.parse_args()
    if a.crop:
        crop(a.out, a.crop[0], int(a.crop[1]), [float(v) for v in a.crop[2:]])
    else:
        render(a.out)


if __name__ == "__main__":
    main()
