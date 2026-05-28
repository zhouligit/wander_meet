"""软著鉴别材料：与 R11 申请表保持一致的名称与路径（去旅聚）。

本件登记对象为移动终端 App 客户端软件（与小程序、网页版为不同登记事项）。
软件全称须与版权中心申请表逐字一致；修改全称后须重生成程序/文档鉴别 PDF。
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_SRC = (REPO_ROOT.parent / "lv_ju" / "travel-together" / "src").resolve()

# 与申请表「软件全称」一致（App 类，全称以 App 结尾）
SOFT_FULL_NAME = "去旅聚户外活动报名与社交App软件"
SOFT_SHORT_NAME = "去旅聚"
SOFT_PLATFORM_LABEL = "App"
VERSION = "V1.0"
COPYRIGHT_HOLDER = "枣庄禾跃科技有限公司"
COPYRIGHT_HOLDER_LINE = f"著作权人（开发单位）：{COPYRIGHT_HOLDER}"

# 程序鉴别、文档鉴别每页页眉须与 R11 申请表「软件全称」「版本号」逐字一致（勿改空格与「V」）
def page_header_left() -> str:
    return f"{SOFT_FULL_NAME}  {VERSION}"

LINES_PER_PAGE = 50
PAGES_FRONT = 30
PAGES_BACK = 30
TOTAL_PROGRAM_PAGES = PAGES_FRONT + PAGES_BACK

MANUAL_SOURCE = REPO_ROOT / "doc" / "soft_registration" / "manual_content_zh.txt"
SCREENSHOTS_DIR = REPO_ROOT / "doc" / "soft_registration" / "screenshots"
DIST_DIR = REPO_ROOT / "dist" / "soft_registration"
DIST_PDF_DIR = DIST_DIR / "pdf"
OUT_DOC_DIR = REPO_ROOT / "doc" / "soft_registration"
