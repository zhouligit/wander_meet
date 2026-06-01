#!/usr/bin/env python3
"""
将 source_front.txt + source_back.txt 排版为程序鉴别材料 PDF：
连续 60 页（前 30 + 后 30），每页 50 行源程序；左侧行号，正文不含顶部说明块。

用法（wander_meet 根目录）：
  python3 scripts/soft_registration_export.py --frontend ../lv_ju/travel-together/src
  python3 scripts/sanitize_soft_registration_outputs.py
  python3 scripts/build_soft_registration_pdf.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from soft_reg_config import (
    COPYRIGHT_HOLDER,
    DIST_DIR,
    LINES_PER_PAGE,
    OUT_DOC_DIR,
    PAGES_BACK,
    PAGES_FRONT,
    SOFT_FULL_NAME,
    SOFT_SHORT_NAME,
    TOTAL_PROGRAM_PAGES,
    VERSION,
    page_header_left,
)

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_PT = 48
RIGHT_PT = 48
TOP_PT = 44
BOTTOM_PT = 44
HEADER_BAND = 22
LINE_NUM_COL_PT = 34
CODE_LEFT_PT = LEFT_PT + LINE_NUM_COL_PT
FONT_SIZE = 8.5
LINE_NUM_FONT_SIZE = 8
LINE_HEIGHT = 13.6
MAX_CHARS = 96
PAGE_HEADER_RE = re.compile(r"第\s*(\d+)\s*页")


def _find_unicode_font() -> str:
    import os

    env = os.environ.get("WM_SOFT_REG_FONT", "").strip()
    if env and Path(env).is_file():
        return env
    for p in (
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        Path.home() / "Library/Fonts/NotoSansSC-Regular.otf",
    ):
        path = Path(p)
        if path.is_file():
            return str(path)
    raise SystemExit("未找到中文字体，请设置 WM_SOFT_REG_FONT")


def _register_font(path: str) -> str:
    name = "WMRegSans"
    pdfmetrics.registerFont(TTFont(name, path))
    return name


def parse_paginated_txt(path: Path) -> list[list[str]]:
    """从 export 生成的分页 txt 解析出每页恰好 50 行代码。"""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pages: list[list[str]] = []
    i = 0
    while i < len(lines):
        if PAGE_HEADER_RE.search(lines[i]):
            i += 1
            if i < len(lines) and lines[i].strip().startswith("-"):
                i += 1
            chunk: list[str] = []
            while i < len(lines) and not PAGE_HEADER_RE.search(lines[i]):
                chunk.append(lines[i])
                i += 1
            code = chunk[:LINES_PER_PAGE]
            if len(code) < LINES_PER_PAGE:
                code.extend([""] * (LINES_PER_PAGE - len(code)))
            pages.append(code)
        else:
            i += 1
    return pages


def wrap_line(s: str) -> list[str]:
    s = s.expandtabs(4)
    if len(s) <= MAX_CHARS:
        return [s]
    return [s[j : j + MAX_CHARS] for j in range(0, len(s), MAX_CHARS)]


def _load_line_bases(dist: Path) -> tuple[int, int]:
    path = dist / "program_line_bases.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("front", 1)), int(data.get("back", 1))
    return 1, 1


def _line_base_for_page(page_no: int, front_base: int, back_base: int) -> int:
    if page_no <= PAGES_FRONT:
        return front_base + (page_no - 1) * LINES_PER_PAGE
    return back_base + (page_no - PAGES_FRONT - 1) * LINES_PER_PAGE


def render_program_pdf(
    out_path: Path,
    pages: list[list[str]],
    font_name: str,
    *,
    front_line_base: int,
    back_line_base: int,
) -> None:
    if len(pages) != TOTAL_PROGRAM_PAGES:
        raise SystemExit(
            f"需要 {TOTAL_PROGRAM_PAGES} 页源程序，当前解析得到 {len(pages)} 页。"
            f"请确认已运行 soft_registration_export.py 且合并行数足够。"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)
    usable_top = PAGE_HEIGHT - TOP_PT - HEADER_BAND
    usable_bottom = BOTTOM_PT

    for page_no, code_lines in enumerate(pages, start=1):
        if len(code_lines) != LINES_PER_PAGE:
            raise SystemExit(f"第 {page_no} 页行数 {len(code_lines)} != {LINES_PER_PAGE}")

        c.setFont(font_name, 9)
        c.setFillColor(colors.HexColor("#334155"))
        c.drawString(LEFT_PT, PAGE_HEIGHT - TOP_PT + 6, page_header_left()[:96])
        c.drawRightString(PAGE_WIDTH - RIGHT_PT, PAGE_HEIGHT - TOP_PT + 6, f"第 {page_no} 页")

        line_base = _line_base_for_page(page_no, front_line_base, back_line_base)
        for row, raw in enumerate(code_lines):
            y = usable_top - (row + 1) * LINE_HEIGHT
            line_no = line_base + row
            c.setFont(font_name, LINE_NUM_FONT_SIZE)
            c.setFillColor(colors.HexColor("#64748b"))
            c.drawRightString(CODE_LEFT_PT - 6, y, str(line_no))
            c.setFont(font_name, FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawString(CODE_LEFT_PT, y, raw.expandtabs(4)[:MAX_CHARS])
        c.showPage()

    c.save()


def write_cover_txt(dist: Path) -> None:
    text = f"""程序鉴别材料 — 源程序（前30页+后30页）

软件名称：{SOFT_FULL_NAME}
版本号：{VERSION}
著作权人：{COPYRIGHT_HOLDER}
开发完成日期：2026年
源程序语言：Python、JavaScript、Vue 等
提交页数：共 {TOTAL_PROGRAM_PAGES} 页（第1–{PAGES_FRONT}页为前段连续源程序，第{PAGES_FRONT + 1}–{TOTAL_PROGRAM_PAGES}页为后段连续源程序）
每页不少于 {LINES_PER_PAGE} 行。
"""
    (dist / "cover_template.txt").write_text(text, encoding="utf-8")


def main() -> None:
    dist = DIST_DIR
    front_path = dist / "source_front.txt"
    back_path = dist / "source_back.txt"
    if not front_path.is_file() or not back_path.is_file():
        raise SystemExit("请先运行 soft_registration_export.py 与 sanitize_soft_registration_outputs.py")

    front_pages = parse_paginated_txt(front_path)
    back_pages = parse_paginated_txt(back_path)
    print(f"解析页数：前 {len(front_pages)}，后 {len(back_pages)}")

    font_name = _register_font(_find_unicode_font())
    all_pages = front_pages + back_pages
    front_base, back_base = _load_line_bases(dist)

    out_pdf = dist / "pdf" / "program_identification_material.pdf"
    render_program_pdf(
        out_pdf,
        all_pages,
        font_name,
        front_line_base=front_base,
        back_line_base=back_base,
    )
    print("已生成:", out_pdf.resolve(), f"（共 {len(all_pages)} 页）")

    write_cover_txt(dist)
    # 同步到 doc 目录便于递交
    OUT_DOC_DIR.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(out_pdf, OUT_DOC_DIR / "program_identification_material.pdf")
    print("已复制到:", (OUT_DOC_DIR / "program_identification_material.pdf").resolve())


if __name__ == "__main__":
    main()
