#!/usr/bin/env python3
"""
生成「文档鉴别材料」PDF（用户操作手册体例）：A4、页眉软件全称+版本、连续页码。

依赖：pip install -r requirements-soft-reg-pdf.txt

默认读取：doc/soft_registration/manual_content_zh.txt
输出：dist/soft_registration/pdf/documentation_identification_full.pdf

若全文 PDF 页数 ≥60，可同时导出前30页+后30页合并：
  documentation_identification_submit.pdf

用法：
  python3 -m venv .venv-soft-reg && .venv-soft-reg/bin/pip install -r requirements-soft-reg-pdf.txt
  .venv-soft-reg/bin/python scripts/build_doc_identification_pdf.py
  .venv-soft-reg/bin/python scripts/build_doc_identification_pdf.py \\
    --copyright-holder-line "著作权人（开发单位）：某某科技有限公司"

可选依赖 PyPDF2：全文≥60页时自动生成前30+后30合并稿。
"""
from __future__ import annotations

import argparse
import html
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

SOFT_FULL_NAME = "旅聚户外活动报名与社交应用软件"
VERSION = "V1.0"
COPYRIGHT_HOLDER_LINE = "著作权人（开发单位）：枣庄禾跃科技有限公司"


def _find_unicode_font() -> str:
    env = os.environ.get("WM_SOFT_REG_FONT", "").strip()
    if env and Path(env).is_file():
        return env
    for p in (
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        Path.home() / "Library/Fonts/NotoSansSC-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
    ):
        path = Path(p)
        if path.is_file():
            return str(path)
    raise SystemExit("未找到中文字体，请设置 WM_SOFT_REG_FONT=/path/to/font.ttf")


def _escape_xml(s: str) -> str:
    return html.escape(s).replace("\n", "<br/>")


def build_story(font_name: str, body_path: Path, copyright_line: str) -> list:
    raw = body_path.read_text(encoding="utf-8")
    lines = [ln.rstrip() for ln in raw.splitlines()]

    title_style = ParagraphStyle(
        name="ManualTitle",
        fontName=font_name,
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=18,
        textColor=colors.HexColor("#0f172a"),
    )
    h1 = ParagraphStyle(
        name="H1",
        fontName=font_name,
        fontSize=14,
        leading=22,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#1e293b"),
    )
    h2 = ParagraphStyle(
        name="H2",
        fontName=font_name,
        fontSize=11.5,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#334155"),
    )
    body_style = ParagraphStyle(
        name="Body",
        fontName=font_name,
        fontSize=10,
        leading=14.8,
        alignment=TA_LEFT,
        spaceAfter=4,
        firstLineIndent=20,
    )
    center_small = ParagraphStyle(
        name="CenterSmall",
        fontName=font_name,
        fontSize=10,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b"),
    )

    story: list = []

    # 封面
    story.append(Spacer(1, 36 * mm))
    story.append(Paragraph(_escape_xml("用户操作手册"), title_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(_escape_xml(SOFT_FULL_NAME), title_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(_escape_xml(f"版本：{VERSION}"), center_small))
    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph(_escape_xml(copyright_line), body_style))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            _escape_xml(
                "说明：本文档用于软件著作权登记之文档鉴别材料（用户操作类说明）。"
                "插图位置已用文字标注，可在 Word 中替换为实际界面截图后重新导出 PDF。"
            ),
            body_style,
        )
    )
    story.append(PageBreak())

    buf: list[str] = []

    def flush_para() -> None:
        nonlocal buf
        if not buf:
            return
        text = "".join(buf).strip()
        if text:
            story.append(Paragraph(_escape_xml(text), body_style))
        buf = []

    for line in lines:
        s = line.strip()
        if not s:
            flush_para()
            continue
        if s.startswith("## "):
            flush_para()
            story.append(Paragraph(_escape_xml(s[3:].strip()), h1))
            continue
        if s.startswith("### "):
            flush_para()
            story.append(Paragraph(_escape_xml(s[4:].strip()), h2))
            continue
        buf.append(s)
    flush_para()

    return story


def _header_footer(canvas, doc, font_name: str) -> None:
    canvas.saveState()
    canvas.setFont(font_name, 9)
    canvas.setFillColor(colors.HexColor("#334155"))
    w, h = A4
    canvas.drawString(18 * mm, h - 14 * mm, f"{SOFT_FULL_NAME}  {VERSION}")
    canvas.drawRightString(w - 18 * mm, h - 14 * mm, f"第 {canvas.getPageNumber()} 页")
    canvas.restoreState()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("doc/soft_registration/manual_content_zh.txt"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("dist/soft_registration/pdf"))
    parser.add_argument(
        "--copyright-holder-line",
        type=str,
        default="",
        help="封面著作权人行全文，例如：著作权人（开发单位）：某某科技有限公司（须与申请表一致）。不传则使用脚本内默认占位。",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    body_path = root / args.source
    if not body_path.is_file():
        raise SystemExit(f"找不到正文文件: {body_path}")

    font_path = _find_unicode_font()
    font_name = "DocManualFont"
    pdfmetrics.registerFont(TTFont(font_name, font_path))

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cr = (args.copyright_holder_line or "").strip()
    copyright_line = cr if cr else COPYRIGHT_HOLDER_LINE
    story = build_story(font_name, body_path, copyright_line)

    full_pdf = out_dir / "documentation_identification_full.pdf"

    def _on_page(canv, doc):
        _header_footer(canv, doc, font_name)

    doc = SimpleDocTemplate(
        str(full_pdf),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
    )
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)

    print("已生成全文 PDF:", full_pdf.resolve())
    print("封面著作权人取自脚本 COPYRIGHT_HOLDER_LINE；若与申请表不一致，请改脚本或传 --copyright-holder-line 后重跑。")

    # 尝试用 PyPDF2 裁剪前30后30页（可选依赖）
    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(str(full_pdf))
        n = len(reader.pages)
        print(f"全文共 {n} 页。")
        if n >= 60:
            w = PdfWriter()
            for i in range(30):
                w.add_page(reader.pages[i])
            for i in range(n - 30, n):
                w.add_page(reader.pages[i])
            submit_path = out_dir / "documentation_identification_submit.pdf"
            with open(submit_path, "wb") as f:
                w.write(f)
            print("全文≥60页，已额外生成提交用（前30+后30）:", submit_path.resolve())
        else:
            print("全文不足60页：鉴别材料可提交 documentation_identification_full.pdf 完整文档。")
    except ImportError:
        print("提示：安装 PyPDF2 后可自动生成「前30+后30」合并文件：pip install PyPDF2")


if __name__ == "__main__":
    main()
