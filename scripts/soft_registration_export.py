#!/usr/bin/env python3
"""
软著「程序鉴别材料」源码摘录辅助脚本（一般交存：前 30 页 + 后 30 页，每页 50 行）。

名称与版本见 scripts/soft_reg_config.py（当前：去旅聚）。

用法（在项目 wander_meet 根目录）：
  python3 scripts/soft_registration_export.py

默认纳入前端 ../lv_ju/travel-together/src；也可指定：
  python3 scripts/soft_registration_export.py --frontend /path/to/travel-together/src

输出目录：dist/soft_registration/
  - source_concat_full.txt       合并后的完整源码（便于核对总行数）
  - source_front.txt             前 30 页正文（每页 50 行，含页眉占位）
  - source_back.txt              后 30 页正文
  - page_count_report.txt        行数与是否不足 60 页的提示
  - cover_template.txt           首页「文件说明」示例（请按需改写）
  - end_marker.txt               末页结束标志示例

注意：
  - 版权中心对「空行、单行注释是否计入」以当地最新指引为准；本脚本按「原始行」分页，
    提交前请用 Word/WPS 设定 A4、等宽字体、页边距后，人工核对每页可见行数≥50。
  - 切勿把 .env、密钥、令牌写入摘录；提交前全文检索 password、secret、api_key 等。

生成 PDF（需 reportlab，建议独立 venv）：
  python3 -m venv .venv-soft-reg && .venv-soft-reg/bin/pip install -r requirements-soft-reg-pdf.txt
  .venv-soft-reg/bin/python scripts/sanitize_soft_registration_outputs.py
  .venv-soft-reg/bin/python scripts/build_soft_registration_pdf.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soft_reg_config import (  # noqa: E402
    COPYRIGHT_HOLDER,
    DEFAULT_FRONTEND_SRC,
    DIST_DIR,
    LINES_PER_PAGE,
    PAGES_BACK,
    PAGES_FRONT,
    SOFT_FULL_NAME,
    SOFT_SHORT_NAME,
    VERSION,
    page_header_left,
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "unpackage",
    "dist",
    ".idea",
    ".vscode",
}
SKIP_FILE_SUFFIXES = (".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip")

BACKEND_SUFFIXES = {".py"}
FRONTEND_SUFFIXES = {".vue", ".js", ".scss", ".ts", ".json"}


def iter_source_files(root: Path, suffixes: set[str]) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in suffixes and not fn.endswith(SKIP_FILE_SUFFIXES):
                out.append(p)
    out.sort(key=lambda x: str(x))
    return out


def preferred_backend_order(files: list[Path]) -> list[Path]:
    """入口与路由靠前，便于体现核心逻辑开头。"""
    priority = [
        "app/main.py",
        "app/api/router.py",
        "app/core/config.py",
        "app/db/session.py",
        "app/api/deps.py",
        "app/api/v1/endpoints/activities.py",
        "app/api/v1/endpoints/auth.py",
        "app/api/v1/endpoints/me.py",
    ]
    pri_set = {p.replace("/", os.sep) for p in priority}
    front = []
    rest = []
    seen = set()
    for rel in priority:
        for f in files:
            if str(f).endswith(rel) or str(f).replace("\\", "/").endswith(rel):
                if f not in seen:
                    front.append(f)
                    seen.add(f)
                break
    for f in files:
        if f not in seen:
            rest.append(f)
    return front + rest


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


def read_concat(
    paths: Iterable[Path], root_hint: str, repo_root: Path
) -> tuple[list[str], list[tuple[str, int]]]:
    """返回全部行 + (文件标记, 起始行号) 映射便于核对。"""
    lines: list[str] = []
    index: list[tuple[str, int]] = []
    marker = f"# ---------- [{root_hint}] ----------"
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = _display_path(path, repo_root)
        index.append((rel, len(lines) + 1))
        lines.append(marker)
        lines.append(f"# FILE: {rel}")
        lines.extend(text.splitlines())
        lines.append("")
    return lines, index


def source_preamble() -> list[str]:
    """源程序说明（单独文件，不写入鉴别材料 PDF 正文）。"""
    bar = "# " + "=" * 72
    return [
        bar,
        f"# 软件全称：{SOFT_FULL_NAME}",
        f"# 软件简称：{SOFT_SHORT_NAME}",
        f"# 版本号：{VERSION}",
        f"# 著作权人：{COPYRIGHT_HOLDER}",
        "# 本摘录为程序鉴别材料（前30页+后30页源程序，每页50行）",
        bar,
        "",
    ]


def paginate_with_header(
    chunk_lines: list[str],
    start_page_number: int,
) -> list[str]:
    out: list[str] = []
    page = start_page_number
    i = 0
    n = len(chunk_lines)
    header_width = 76
    while i < n:
        header = page_header_left()
        # 简化页眉：左全称版本，右页码（打印时再对齐）
        line1 = f"{header:<{header_width}}第 {page} 页"
        out.append(line1)
        out.append("-" * 88)
        for _ in range(LINES_PER_PAGE):
            if i < n:
                out.append(chunk_lines[i])
                i += 1
            else:
                out.append("")
        out.append("")
        page += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frontend",
        type=str,
        default=str(DEFAULT_FRONTEND_SRC) if DEFAULT_FRONTEND_SRC.is_dir() else "",
        help="前端 src 目录，将合并 .vue/.js/.scss（不含 node_modules）",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = DIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 正文摘录不含顶部说明块（说明见 cover_template / source_preamble.txt）
    all_segments: list[str] = []
    report_lines: list[str] = []

    # Backend
    app_root = repo_root / "app"
    alembic_root = repo_root / "alembic"
    backend_files: list[Path] = []
    if app_root.is_dir():
        backend_files.extend(iter_source_files(app_root, BACKEND_SUFFIXES))
    if alembic_root.is_dir():
        backend_files.extend(iter_source_files(alembic_root, BACKEND_SUFFIXES))
    backend_files = list(dict.fromkeys(backend_files))
    backend_files = preferred_backend_order(backend_files)

    blines, bidx = read_concat(backend_files, "backend", repo_root)
    all_segments.extend(blines)
    report_lines.append(f"后端文件数: {len(backend_files)}，合并行数: {len(blines)}")

    # Frontend (optional)
    if args.frontend:
        fr = Path(args.frontend).expanduser().resolve()
        if fr.is_dir():
            ff = iter_source_files(fr, FRONTEND_SUFFIXES)
            flines, _ = read_concat(ff, "frontend", repo_root)
            all_segments.extend(flines)
            report_lines.append(f"前端目录: {fr}")
            report_lines.append(f"前端文件数: {len(ff)}，合并行数: {len(flines)}")
        else:
            report_lines.append(f"警告: 前端路径不存在，已跳过: {args.frontend}")

    total_lines = len(all_segments)
    need_front = PAGES_FRONT * LINES_PER_PAGE
    need_back = PAGES_BACK * LINES_PER_PAGE
    need_all = need_front + need_back

    report_lines.insert(0, f"软件名称（脚本内配置）: {SOFT_FULL_NAME}")
    report_lines.insert(1, f"版本: {VERSION}")
    report_lines.append(f"合并总行数（含分隔注释）: {total_lines}")

    if total_lines <= need_all:
        report_lines.append("")
        report_lines.append(
            "【提示】合并行数 ≤ 前30页+后30页所需行数（1500+1500），按规则「不足 60 页全部提交」。"
            "请将 source_concat_full.txt 全文排版为 PDF，不必强行拆前后。"
        )
        front_chunk = all_segments
        back_chunk: list[str] = []
    else:
        front_chunk = all_segments[:need_front]
        back_chunk = all_segments[-need_back:]

    back_line_start = len(all_segments) - need_back + 1 if back_chunk else 1
    (out_dir / "program_line_bases.json").write_text(
        json.dumps({"front": 1, "back": back_line_start}, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "source_preamble.txt").write_text(
        "\n".join(source_preamble()) + "\n", encoding="utf-8"
    )
    (out_dir / "source_concat_full.txt").write_text("\n".join(all_segments) + "\n", encoding="utf-8")
    (out_dir / "source_front.txt").write_text(
        "\n".join(paginate_with_header(front_chunk, 1)) + "\n",
        encoding="utf-8",
    )
    if back_chunk:
        start_page = PAGES_FRONT + 1
        (out_dir / "source_back.txt").write_text(
            "\n".join(paginate_with_header(back_chunk, start_page)) + "\n",
            encoding="utf-8",
        )
    else:
        (out_dir / "source_back.txt").write_text(
            "（全文已不足 60 页，仅使用 source_concat_full.txt 全交）\n", encoding="utf-8"
        )

    from soft_reg_config import COPYRIGHT_HOLDER, TOTAL_PROGRAM_PAGES

    cover = f"""程序鉴别材料 — 源程序说明（与正文 PDF 一并递交）

软件名称：{SOFT_FULL_NAME}
版本号：{VERSION}
著作权人：{COPYRIGHT_HOLDER}

本材料为上述软件源程序的鉴别材料（一般交存），共提交 {TOTAL_PROGRAM_PAGES} 页：
第 1–{PAGES_FRONT} 页为连续源程序前段，第 {PAGES_FRONT + 1}–{TOTAL_PROGRAM_PAGES} 页为连续源程序后段；
每页不少于 {LINES_PER_PAGE} 行。语言含 Python、JavaScript、Vue 等。

---
"""
    (out_dir / "cover_template.txt").write_text(cover, encoding="utf-8")
    (out_dir / "end_marker.txt").write_text(
        f"\n\n/* ========== 源程序摘录结束 {SOFT_FULL_NAME} {VERSION} ========== */\n",
        encoding="utf-8",
    )
    (out_dir / "page_count_report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("已生成:", out_dir)
    for name in (
        "source_concat_full.txt",
        "source_front.txt",
        "source_back.txt",
        "cover_template.txt",
        "end_marker.txt",
        "page_count_report.txt",
    ):
        print(" -", name)


if __name__ == "__main__":
    main()
