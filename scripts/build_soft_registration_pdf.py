#!/usr/bin/env python3
"""
将 dist/soft_registration 下的 txt 排版为「程序鉴别材料」PDF（A4、页眉、页码）。

依赖：pip install -r requirements-soft-reg-pdf.txt

字体：环境变量 WM_SOFT_REG_FONT；否则 macOS 尝试 Arial Unicode.ttf。

用法（在 wander_meet 根目录）：
  pip install -r requirements-soft-reg-pdf.txt
  python3 scripts/build_soft_registration_pdf.py
  python3 scripts/build_soft_registration_pdf.py --mode merged

请修改 SOFT_FULL_NAME / VERSION 与 R11 申请表一致。
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

SOFT_FULL_NAME = "旅聚户外活动报名与社交应用软件"
VERSION = "V1.0"

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_PT = 52
RIGHT_PT = 52
TOP_PT = 52
BOTTOM_PT = 52
HEADER_BAND = 24
FONT_SIZE = 8
LINE_HEIGHT = float(FONT_SIZE) * 1.42
MAX_CHARS_PER_LINE = 106


def _find_unicode_font() -> str:
    env = os.environ.get("WM_SOFT_REG_FONT", "").strip()
    if env and Path(env).is_file():
        return env
    candidates = [
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        Path.home() / "Library/Fonts/NotoSansSC-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf",
    ]
    for p in candidates:
        path = Path(p) if isinstance(p, Path) else Path(str(p))
        if path.is_file():
            return str(path)
    raise SystemExit(
        "未找到中文字体。请安装 Noto Sans SC，或设置 WM_SOFT_REG_FONT=/绝对路径/字体.ttf"
    )


def _register_font(path: str) -> str:
    name = "WMRegSans"
    pdfmetrics.registerFont(TTFont(name, path))
    return name


def strip_builtin_page_headers(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(lines)
    pat = re.compile(r"第\s*\d+\s*页\s*$")
    while i < n:
        line = lines[i]
        if i + 1 < n and pat.search(line) and lines[i + 1].strip().startswith("-"):
            i += 2
            continue
        out.append(line.rstrip("\n"))
        i += 1
    return out


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def wrap_line(s: str) -> list[str]:
    if len(s) <= MAX_CHARS_PER_LINE:
        return [s]
    return [s[i : i + MAX_CHARS_PER_LINE] for i in range(0, len(s), MAX_CHARS_PER_LINE)]


def render_pdf(out_path: Path, lines: list[str], font_name: str, start_page: int = 1) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)

    usable_top = PAGE_HEIGHT - TOP_PT - HEADER_BAND
    usable_bottom = BOTTOM_PT
    max_lines = max(35, int((usable_top - usable_bottom) / LINE_HEIGHT))

    page_no = start_page

    def draw_header() -> None:
        c.setFont(font_name, 9)
        c.setFillColor(colors.HexColor("#0f172a"))
        c.drawString(LEFT_PT, PAGE_HEIGHT - TOP_PT + 8, f"{SOFT_FULL_NAME}  {VERSION}"[:96])
        c.drawRightString(PAGE_WIDTH - RIGHT_PT, PAGE_HEIGHT - TOP_PT + 8, f"第 {page_no} 页")

    def new_page() -> None:
        nonlocal page_no
        c.showPage()
        page_no += 1
        draw_header()

    draw_header()
    used = 0

    for raw in lines:
        for part in wrap_line(raw.expandtabs(4)):
            if used >= max_lines:
                new_page()
                used = 0
            y = usable_top - (used + 1) * LINE_HEIGHT
            c.setFont(font_name, FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawString(LEFT_PT, y, part)
            used += 1

    c.save()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist/soft_registration"))
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--mode",
        choices=("split", "merged"),
        default="split",
        help="split：前30、后30各一个PDF；merged：封面+前+后+结束标记，连续页码一个PDF",
    )
    parser.add_argument("--no-strip-headers", action="store_true")
    args = parser.parse_args()

    dist = args.dist
    out_dir = args.out_dir or (dist / "pdf")
    font_path = _find_unicode_font()
    font_name = _register_font(font_path)
    print("字体:", font_path)

    front_path = dist / "source_front.txt"
    back_path = dist / "source_back.txt"
    cover_path = dist / "cover_template.txt"
    end_path = dist / "end_marker.txt"

    if not front_path.is_file() or not back_path.is_file():
        raise SystemExit("请先运行 python3 scripts/soft_registration_export.py 生成 txt")

    front_lines = read_lines(front_path)
    back_lines = read_lines(back_path)
    if not args.no_strip_headers:
        front_lines = strip_builtin_page_headers(front_lines)
        back_lines = strip_builtin_page_headers(back_lines)

    if args.mode == "split":
        p_front = out_dir / "program_source_front.pdf"
        p_back = out_dir / "program_source_back.pdf"
        render_pdf(p_front, front_lines, font_name, start_page=1)
        render_pdf(p_back, back_lines, font_name, start_page=1)
        print("已生成:", p_front.resolve())
        print("已生成:", p_back.resolve())
        print("说明：两个文件页码均从第 1 页开始；若网站要求一套连续页码，请改用 --mode merged。")
        return

    merged_lines: list[str] = []
    if cover_path.is_file():
        merged_lines.extend(read_lines(cover_path))
        merged_lines.extend(["", "---", ""])
    merged_lines.extend(front_lines)
    merged_lines.extend(["", "--- （以下为后 30 页对应源码）---", ""])
    merged_lines.extend(back_lines)
    if end_path.is_file():
        merged_lines.extend(["", "---", ""])
        merged_lines.extend(read_lines(end_path))

    merged_pdf = out_dir / "program_identification_material.pdf"
    render_pdf(merged_pdf, merged_lines, font_name, start_page=1)
    print("已生成:", merged_pdf.resolve())


if __name__ == "__main__":
    main()
