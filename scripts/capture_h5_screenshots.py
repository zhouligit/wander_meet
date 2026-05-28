#!/usr/bin/env python3
"""
从 travel-together H5 开发服截取界面图（390×844，2x），写入 doc/soft_registration/screenshots/。

依赖：pip install playwright && playwright install chromium
前置：在 lv_ju/travel-together 已 npm install

用法（wander_meet 根目录）：
  python3 scripts/capture_h5_screenshots.py
  python3 scripts/capture_h5_screenshots.py --base-url http://127.0.0.1:5173
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from soft_reg_config import DEFAULT_FRONTEND_SRC, SCREENSHOTS_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = DEFAULT_FRONTEND_SRC.parent

# (输出文件名, hash 路由, 进入前是否清空登录态)
ROUTES: list[tuple[str, str, bool]] = [
    ("login.png", "/pages/login/login", True),
    ("home.png", "/pages/home/home", False),
    ("onboarding.png", "/pages/profile-edit/profile-edit?first=1", False),
    ("detail.png", "/pages/activity-detail/activity-detail?id=1", False),
    ("publish.png", "/pages/publish/publish", False),
    ("discover.png", "/pages/discover/discover", False),
    ("activity_list.png", "/pages/activity-list/activity-list", False),
    ("my_activities.png", "/pages/my-activity-list/my-activity-list", False),
    ("hosted_list.png", "/pages/hosted-activity-list/hosted-activity-list", False),
    ("location_picker.png", "/pages/location-picker/location-picker", False),
    ("messages.png", "/pages/messages/messages", False),
    ("profile.png", "/pages/profile/profile", False),
    ("privacy.png", "/pages/privacy-policy/privacy-policy", False),
    ("community_rules.png", "/pages/community-rules/community-rules", False),
    ("entry.png", "/pages/home/home", False),
]

VIEWPORT = {"width": 390, "height": 844}
DEVICE_SCALE = 2


def _inject_storage(page, *, logged_in: bool) -> None:
    page.evaluate(
        """(loggedIn) => {
      localStorage.setItem('wm_use_mock', 'true');
      if (loggedIn) {
        localStorage.setItem('wm_access_token', 'mock_access_token_for_screenshot');
        localStorage.setItem('wm_refresh_token', 'mock_refresh_token_for_screenshot');
      } else {
        localStorage.removeItem('wm_access_token');
        localStorage.removeItem('wm_refresh_token');
      }
    }""",
        logged_in,
    )


def _wait_ready(page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass


def capture_all(base_url: str, out_dir: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "请先安装: pip install playwright && playwright install chromium"
        ) from e

    out_dir.mkdir(parents=True, exist_ok=True)
    backup = out_dir.parent / "screenshots_mock_backup"
    if out_dir.exists() and not backup.exists():
        shutil.copytree(out_dir, backup)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
            locale="zh-CN",
        )
        page = context.new_page()
        origin = base_url.rstrip("/") + "/"
        page.goto(origin, wait_until="domcontentloaded", timeout=60000)

        for filename, route, clear_login in ROUTES:
            _inject_storage(page, logged_in=not clear_login)
            url = f"{base_url.rstrip('/')}/#/{route.lstrip('/')}"
            print("截图:", filename, "<-", url)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            _wait_ready(page)
            dest = out_dir / filename
            page.screenshot(path=str(dest), full_page=False)
            print("  ->", dest, f"({dest.stat().st_size // 1024} KB)")

        # 聊天详情（活动群）
        _inject_storage(page, logged_in=True)
        url = f"{base_url.rstrip('/')}/#/pages/chat-detail/chat-detail?id=1"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        _wait_ready(page)
        chat_path = out_dir / "chat.png"
        page.screenshot(path=str(chat_path), full_page=False)
        print("截图: chat.png ->", chat_path)

        browser.close()

    _postprocess(out_dir)


def _add_phone_frame(path: Path) -> None:
    """为软著材料加手机外框，体现完整手机端界面截图。"""
    from PIL import Image, ImageDraw

    img = Image.open(path).convert("RGB")
    w, h = img.size
    top_bar = max(12, h // 40)
    side = max(10, w // 28)
    out_w = w + side * 2
    out_h = h + top_bar + side * 2
    framed = Image.new("RGB", (out_w, out_h), "#0f172a")
    framed.paste(img, (side, top_bar + side))
    draw = ImageDraw.Draw(framed)
    radius = max(18, w // 18)
    draw.rounded_rectangle(
        [4, 4, out_w - 5, out_h - 5],
        radius=radius,
        outline="#94a3b8",
        width=3,
    )
    # 顶部状态栏示意
    draw.rectangle([side + 8, side, out_w - side - 8, top_bar + side - 4], fill="#1e293b")
    framed.save(path, quality=92)


def _postprocess(out_dir: Path) -> None:
    from PIL import Image

    for p in sorted(out_dir.glob("*.png")):
        if p.name in ("tabbar.png", "flow.png", "detail_compare.png"):
            continue
        _add_phone_frame(p)

    home = out_dir / "home.png"
    if home.is_file():
        img = Image.open(home)
        w, h = img.size
        tab = img.crop((0, int(h * 0.88), w, h))
        tab.save(out_dir / "tabbar.png")

    parts = []
    for name in ("home.png", "detail.png", "messages.png"):
        p = out_dir / name
        if p.is_file():
            im = Image.open(p).resize((195, 422))
            parts.append(im)
    if len(parts) >= 3:
        flow = Image.new("RGB", (390, 844), "#f8fafc")
        flow.paste(parts[0], (0, 0))
        flow.paste(parts[1], (195, 0))
        flow.paste(parts[2], (0, 422))
        flow.save(out_dir / "flow.png")

    # 消息列表与聊天：手册「消息列表与聊天」用 messages；对比图复用 detail
    detail = out_dir / "detail.png"
    if detail.is_file():
        shutil.copy2(detail, out_dir / "detail_compare.png")


def start_dev_server() -> subprocess.Popen | None:
    if not FRONTEND_ROOT.is_dir():
        return None
    print("启动 H5 开发服:", FRONTEND_ROOT)
    proc = subprocess.Popen(
        ["npm", "run", "dev:h5", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=str(FRONTEND_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    for _ in range(60):
        time.sleep(1)
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise SystemExit(f"H5 开发服启动失败:\n{err}")
        try:
            import urllib.request

            urllib.request.urlopen("http://127.0.0.1:5173/", timeout=2)
            print("H5 开发服已就绪")
            return proc
        except Exception:
            continue
    proc.kill()
    raise SystemExit("等待 H5 开发服超时（60s）")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--no-server", action="store_true", help="不自动启动 npm dev:h5")
    args = parser.parse_args()

    browsers = REPO_ROOT / ".pw-browsers"
    if browsers.is_dir() and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)

    proc = None
    if not args.no_server:
        proc = start_dev_server()
    try:
        capture_all(args.base_url, SCREENSHOTS_DIR)
        print("\n完成。截图目录:", SCREENSHOTS_DIR.resolve())
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    main()
