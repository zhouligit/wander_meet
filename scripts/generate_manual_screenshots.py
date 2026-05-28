#!/usr/bin/env python3
"""生成用户手册用界面示意图（PNG），供文档鉴别材料嵌入。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from soft_reg_config import SCREENSHOTS_DIR, SOFT_SHORT_NAME

W, H = 390, 844


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in (
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _card(draw: ImageDraw.ImageDraw, y: int, h: int, fill: str = "#ffffff") -> int:
    draw.rounded_rectangle((16, y, W - 16, y + h), radius=16, fill=fill, outline="#e2e8f0")
    return y + h + 12


def _tabbar(draw: ImageDraw.ImageDraw, active: int = 0) -> None:
    draw.rectangle((0, H - 88, W, H), fill="#ffffff", outline="#e2e8f0")
    labels = ("首页", "发现", "发布", "消息", "我的")
    w = W // 5
    for i, lb in enumerate(labels):
        color = "#0284c7" if i == active else "#94a3b8"
        draw.text((i * w + w // 2 - 12, H - 56), lb, fill=color, font=_font(12))


def _screen_base(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), "#f0f9ff")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 120), fill="#e0f2fe")
    draw.text((20, 48), title, fill="#0f172a", font=_font(22))
    if subtitle:
        draw.text((20, 82), subtitle, fill="#64748b", font=_font(13))
    return img, draw


def shot_entry() -> None:
    img, draw = _screen_base("搜索", "软件入口")
    draw.rounded_rectangle((16, 140, W - 16, 200), radius=12, fill="#ffffff", outline="#cbd5e1")
    draw.text((28, 168), f"搜索：{SOFT_SHORT_NAME}", fill="#334155", font=_font(16))
    draw.text((28, 230), f"「{SOFT_SHORT_NAME}」", fill="#0ea5e9", font=_font(18))
    draw.text((28, 262), "同城活动 · 报名 · 群聊", fill="#94a3b8", font=_font(13))
    img.save(SCREENSHOTS_DIR / "entry.png")


def shot_home() -> None:
    img, draw = _screen_base(SOFT_SHORT_NAME, "广州 · 今天就能找到人")
    y = 130
    draw.rounded_rectangle((16, y, W - 16, y + 88), radius=16, fill="#eef2ff", outline="#c7d2fe")
    draw.text((28, y + 16), "【广州】同城群", fill="#312e81", font=_font(15))
    draw.text((28, y + 44), "找到同城的旅人，进群随时聊", fill="#475569", font=_font(12))
    y += 100
    for i in range(3):
        y = _card(draw, y, 96)
        draw.text((28, y - 84), f"周末 Citywalk · 天河", fill="#0f172a", font=_font(14))
        draw.text((28, y - 58), "周六 14:00 · 体育西路", fill="#64748b", font=_font(12))
    _tabbar(draw)
    img.save(SCREENSHOTS_DIR / "home.png")


def shot_login() -> None:
    img, draw = _screen_base(f"登录{SOFT_SHORT_NAME}")
    y = 180
    draw.text((28, y), "手机号", fill="#334155", font=_font(14))
    y += 28
    draw.rounded_rectangle((16, y, W - 16, y + 48), radius=12, fill="#fff", outline="#e2e8f0")
    draw.text((28, y + 14), "138****0000", fill="#0f172a", font=_font(15))
    y += 64
    draw.text((28, y), "验证码", fill="#334155", font=_font(14))
    y += 28
    draw.rounded_rectangle((16, y, W - 16, y + 48), radius=12, fill="#fff", outline="#e2e8f0")
    draw.text((28, y + 14), "请输入验证码", fill="#94a3b8", font=_font(14))
    y += 72
    draw.rounded_rectangle((16, y, W - 16, y + 48), radius=24, fill="#0284c7")
    draw.text((W // 2 - 24, y + 14), "登录", fill="#fff", font=_font(16))
    img.save(SCREENSHOTS_DIR / "login.png")


def shot_onboarding() -> None:
    img, draw = _screen_base("完善资料", "首次登录引导")
    y = 160
    draw.text((28, y), "昵称", fill="#334155", font=_font(14))
    y += 36
    draw.rounded_rectangle((16, y, W - 16, y + 44), radius=12, fill="#fff", outline="#e2e8f0")
    draw.text((28, y + 12), "旅友小林", fill="#0f172a", font=_font(14))
    y += 60
    draw.text((28, y), "兴趣标签", fill="#334155", font=_font(14))
    y += 32
    for tag in ("Citywalk", "摄影", "约饭"):
        draw.rounded_rectangle((16 + 0, y, 110, y + 32), radius=16, fill="#dbeafe")
        draw.text((28, y + 8), tag, fill="#1d4ed8", font=_font(12))
        y += 40
    draw.rounded_rectangle((16, 720, W - 16, 768), radius=24, fill="#0284c7")
    draw.text((W // 2 - 40, 736), "进入去旅聚", fill="#fff", font=_font(15))
    img.save(SCREENSHOTS_DIR / "onboarding.png")


def shot_detail() -> None:
    img, draw = _screen_base("活动详情")
    y = 130
    draw.text((28, y), "周末天河 Citywalk", fill="#0f172a", font=_font(18))
    y += 36
    draw.text((28, y), "3月15日 14:00 · 体育西路", fill="#64748b", font=_font(13))
    y += 40
    y = _card(draw, y, 72)
    draw.text((28, y - 58), "已报名 4 / 8 人", fill="#334155", font=_font(14))
    draw.rounded_rectangle((16, 760, W - 16, 808), radius=24, fill="#10b981")
    draw.text((W // 2 - 28, 778), "报名", fill="#fff", font=_font(16))
    img.save(SCREENSHOTS_DIR / "detail.png")


def shot_publish() -> None:
    img, draw = _screen_base("发布活动")
    fields = ("活动标题", "分类", "开始时间", "地点", "人数上限")
    y = 120
    for label in fields:
        draw.text((28, y), label, fill="#475569", font=_font(13))
        y += 22
        draw.rounded_rectangle((16, y, W - 16, y + 40), radius=10, fill="#fff", outline="#e2e8f0")
        y += 52
    draw.rounded_rectangle((16, 760, W - 16, 808), radius=24, fill="#6366f1")
    draw.text((W // 2 - 28, 778), "发布", fill="#fff", font=_font(16))
    img.save(SCREENSHOTS_DIR / "publish.png")


def shot_discover() -> None:
    img, draw = _screen_base("发现")
    y = 130
    for cat in ("咖啡", "徒步", "桌游", "Citywalk"):
        draw.rounded_rectangle((16, y, 90, y + 36), radius=18, fill="#e0f2fe")
        draw.text((30, y + 10), cat, fill="#0369a1", font=_font(13))
        y += 48
    y = _card(draw, y + 8, 80)
    draw.text((28, y - 66), "分类活动列表", fill="#0f172a", font=_font(14))
    _tabbar(draw)
    img.save(SCREENSHOTS_DIR / "discover.png")


def shot_my_activities() -> None:
    img, draw = _screen_base("我的活动")
    y = 130
    for t in ("已参加 · 周末徒步", "已发起 · 咖啡交流"):
        y = _card(draw, y, 72)
        draw.text((28, y - 56), t, fill="#0f172a", font=_font(14))
    img.save(SCREENSHOTS_DIR / "my_activities.png")


def shot_messages() -> None:
    img, draw = _screen_base("消息")
    y = 130
    for t, sub in (("活动群聊 · Citywalk", "小明：明天见"), ("私聊 · 阿花", "好的")):
        y = _card(draw, y, 68)
        draw.text((28, y - 52), t, fill="#0f172a", font=_font(14))
        draw.text((28, y - 28), sub, fill="#94a3b8", font=_font(12))
    _tabbar(draw, active=3)
    img.save(SCREENSHOTS_DIR / "messages.png")


def shot_profile() -> None:
    img, draw = _screen_base("我的")
    draw.ellipse((W // 2 - 40, 120, W // 2 + 40, 200), fill="#c7d2fe")
    draw.text((W // 2 - 28, 220), "旅友小林", fill="#0f172a", font=_font(18))
    y = 280
    for item in ("绑定手机号", "历史活动", "意见与建议", "社区规范"):
        y = _card(draw, y, 48)
        draw.text((28, y - 38), item, fill="#334155", font=_font(14))
    _tabbar(draw, active=4)
    img.save(SCREENSHOTS_DIR / "profile.png")


def shot_privacy() -> None:
    img, draw = _screen_base("隐私政策")
    y = 130
    para = (
        f"欢迎使用{SOFT_SHORT_NAME}。我们重视您的个人信息保护，",
        "本政策说明我们如何收集、使用与存储相关信息。",
        "使用本软件即表示您已阅读并同意本政策。",
    )
    for line in para:
        draw.text((24, y), line, fill="#334155", font=_font(13))
        y += 28
    img.save(SCREENSHOTS_DIR / "privacy.png")


def shot_tabbar() -> None:
    img = Image.new("RGB", (W, 120), "#f8fafc")
    draw = ImageDraw.Draw(img)
    _tabbar(draw, active=0)
    img.save(SCREENSHOTS_DIR / "tabbar.png")


def shot_flow() -> None:
    """四联屏示意：首页 → 详情 → 报名 → 消息"""
    img = Image.new("RGB", (W, H), "#f8fafc")
    draw = ImageDraw.Draw(img)
    draw.text((20, 24), "典型流程示意", fill="#0f172a", font=_font(18))
    panels = ("首页浏览", "活动详情", "报名成功", "进入群聊")
    y = 60
    for p in panels:
        draw.rounded_rectangle((16, y, W - 16, y + 160), radius=12, fill="#fff", outline="#e2e8f0")
        draw.text((28, y + 68), p, fill="#334155", font=_font(15))
        y += 176
    img.save(SCREENSHOTS_DIR / "flow.png")


def main() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    shot_entry()
    shot_home()
    shot_login()
    shot_onboarding()
    shot_detail()
    shot_publish()
    shot_discover()
    shot_my_activities()
    shot_messages()
    shot_profile()
    shot_privacy()
    shot_tabbar()
    shot_flow()
    print("已生成界面截图:", SCREENSHOTS_DIR.resolve())


if __name__ == "__main__":
    main()
