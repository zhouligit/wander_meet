"""软著鉴别材料：与 R11 申请表保持一致的名称与路径（去旅聚）。"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_SRC = (REPO_ROOT.parent / "lv_ju" / "travel-together" / "src").resolve()

SOFT_FULL_NAME = "去旅聚户外活动报名与社交应用软件"
SOFT_SHORT_NAME = "去旅聚"
VERSION = "V1.0"
COPYRIGHT_HOLDER = "枣庄禾跃科技有限公司"
COPYRIGHT_HOLDER_LINE = f"著作权人（开发单位）：{COPYRIGHT_HOLDER}"

LINES_PER_PAGE = 50
PAGES_FRONT = 30
PAGES_BACK = 30
TOTAL_PROGRAM_PAGES = PAGES_FRONT + PAGES_BACK

MANUAL_SOURCE = REPO_ROOT / "doc" / "soft_registration" / "manual_content_zh.txt"
SCREENSHOTS_DIR = REPO_ROOT / "doc" / "soft_registration" / "screenshots"
DIST_DIR = REPO_ROOT / "dist" / "soft_registration"
DIST_PDF_DIR = DIST_DIR / "pdf"
OUT_DOC_DIR = REPO_ROOT / "doc" / "soft_registration"
