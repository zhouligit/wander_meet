#!/usr/bin/env python3
"""
生成文档鉴别材料 PDF（用户操作手册）：嵌入界面截图，满足图文对照要求。

用法：
  python3 scripts/generate_manual_screenshots.py
  python3 scripts/build_doc_identification_pdf.py
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from soft_reg_config import (
    COPYRIGHT_HOLDER_LINE,
    MANUAL_SOURCE,
    OUT_DOC_DIR,
    SCREENSHOTS_DIR,
    SOFT_FULL_NAME,
    SOFT_PLATFORM_LABEL,
    SOFT_SHORT_NAME,
    page_header_left,
    VERSION,
)

SCREENSHOT_PLACEHOLDER_RE = re.compile(r"【此处插入截图[：:](.+?)】")

# 截图说明关键字 → 文件名（doc/soft_registration/screenshots/）
CAPTION_TO_FILE: list[tuple[str, str]] = [
    ("App主界面首页", "home.png"),
    ("App首页活动列表", "home.png"),
    ("App首页", "home.png"),
    ("App登录页", "login.png"),
    ("手机号登录", "login.png"),
    ("App底部主导航", "tabbar.png"),
    ("底部主导航", "tabbar.png"),
    ("App发现页", "discover.png"),
    ("发现页", "discover.png"),
    ("App全部活动列表", "activity_list.png"),
    ("全部活动列表", "activity_list.png"),
    ("App活动详情报名", "detail.png"),
    ("App活动详情页", "detail.png"),
    ("活动详情页", "detail.png"),
    ("App发布活动表单", "publish.png"),
    ("发布活动", "publish.png"),
    ("App选择活动地点", "location_picker.png"),
    ("选择活动地点", "location_picker.png"),
    ("App发起活动列表", "hosted_list.png"),
    ("发起活动列表", "hosted_list.png"),
    ("App我的活动列表", "my_activities.png"),
    ("我的活动列表", "my_activities.png"),
    ("App消息列表", "messages.png"),
    ("消息列表", "messages.png"),
    ("App聊天界面", "chat.png"),
    ("聊天界面", "chat.png"),
    ("App我的页面", "profile.png"),
    ("我的页面", "profile.png"),
    ("App完善资料页", "onboarding.png"),
    ("完善资料", "onboarding.png"),
    ("App隐私政策页", "privacy.png"),
    ("隐私政策", "privacy.png"),
    ("App社区规范页", "community_rules.png"),
    ("社区规范", "community_rules.png"),
    ("App操作流程四联屏", "flow.png"),
    ("操作流程四联屏", "flow.png"),
    ("四联屏", "flow.png"),
]


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


def _escape_xml(s: str) -> str:
    return html.escape(s).replace("\n", "<br/>")


def caption_to_image(caption: str) -> Path | None:
    cap = caption.strip()
    for key, fname in CAPTION_TO_FILE:
        if key in cap:
            p = SCREENSHOTS_DIR / fname
            if p.is_file():
                return p
    fallback = SCREENSHOTS_DIR / "home.png"
    return fallback if fallback.is_file() else None


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
    caption_style = ParagraphStyle(
        name="Cap",
        fontName=font_name,
        fontSize=9,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8,
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
                f"说明：本文档为「{SOFT_SHORT_NAME}」软件著作权登记之文档鉴别材料。"
                f"登记软件全称：{SOFT_FULL_NAME}，版本号 {VERSION}。"
                f"软件形态：移动终端 {SOFT_PLATFORM_LABEL} 客户端。"
                "正文为图文对照操作手册，截图为 App 手机端完整界面。"
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
        m = SCREENSHOT_PLACEHOLDER_RE.fullmatch(s)
        if m:
            flush_para()
            cap = m.group(1).strip()
            img_path = caption_to_image(cap)
            if img_path:
                # 手机端完整截图（390×844 比例）在 A4 上尽量放大展示
                img = RLImage(str(img_path), width=52 * mm, height=112 * mm)
                story.append(Spacer(1, 2 * mm))
                story.append(img)
                story.append(
                    Paragraph(
                        _escape_xml(f"图：{cap}（{SOFT_PLATFORM_LABEL}手机端完整界面）"),
                        caption_style,
                    )
                )
                story.append(Spacer(1, 4 * mm))
            else:
                story.append(Paragraph(_escape_xml(f"（界面截图：{cap}）"), caption_style))
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
    canvas.drawString(18 * mm, h - 14 * mm, page_header_left())
    canvas.drawRightString(w - 18 * mm, h - 14 * mm, f"第 {canvas.getPageNumber()} 页")
    canvas.restoreState()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=MANUAL_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DOC_DIR)
    parser.add_argument("--copyright-holder-line", type=str, default="")
    args = parser.parse_args()

    body_path = args.source
    if not body_path.is_file():
        raise SystemExit(f"找不到正文: {body_path}")
    if not SCREENSHOTS_DIR.is_dir():
        raise SystemExit(f"请先运行 generate_manual_screenshots.py，目录: {SCREENSHOTS_DIR}")

    font_path = _find_unicode_font()
    font_name = "DocManualFont"
    pdfmetrics.registerFont(TTFont(font_name, font_path))

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    copyright_line = (args.copyright_holder_line or "").strip() or COPYRIGHT_HOLDER_LINE

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

    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(full_pdf))
        n = len(reader.pages)
        print("已生成:", full_pdf.resolve())
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
            print("已生成提交用（前30+后30）:", submit_path.resolve())
        else:
            print("全文不足60页：提交 documentation_identification_full.pdf 完整文档即可。")
    except ImportError:
        print("提示：安装 pypdf 后可自动生成前30+后30合并稿")


if __name__ == "__main__":
    main()
