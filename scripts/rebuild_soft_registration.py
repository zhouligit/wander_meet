#!/usr/bin/env python3
"""一键重新生成软著程序/文档鉴别材料（去旅聚 · 补正版）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    run([PY, str(SCRIPTS / "soft_registration_export.py")])
    run([PY, str(SCRIPTS / "sanitize_soft_registration_outputs.py")])
    run([PY, str(SCRIPTS / "build_soft_registration_pdf.py")])
    run([PY, str(SCRIPTS / "capture_h5_screenshots.py")])  # 默认原始截图，不加外框
    run([PY, str(SCRIPTS / "build_doc_identification_pdf.py")])
    print("\n完成。递交文件：")
    print(" - doc/soft_registration/program_identification_material.pdf（60页源程序）")
    print(" - doc/soft_registration/documentation_identification_full.pdf（用户手册+截图，推荐补正）")
    print(" - doc/soft_registration/documentation_identification_submit.pdf（≥60页时的前30+后30版）")
    print(" - 签章页须在版权中心系统单独补正，见 doc/soft_registration/补正递交说明.md")


if __name__ == "__main__":
    main()
