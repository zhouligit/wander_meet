#!/usr/bin/env python3
"""检查百度 BOS 配置（在服务器 /opt/wander_meet 下运行）。

用法:
  cd /opt/wander_meet && source .venv/bin/activate
  python scripts/check_bos_config.py
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from app.core.config import get_settings
        from app.services.bos_storage import (
            bos_is_configured,
            build_bce_read_configuration,
            build_bce_upload_configuration,
        )
    except ImportError:
        print("请在项目根目录、已激活 venv 后运行", file=sys.stderr)
        return 1

    s = get_settings()
    bucket = (s.bos_bucket or "").strip()
    endpoint = (s.bos_endpoint or "").strip()
    public_base = (s.bos_public_base_url or "").strip()
    ak = (s.bos_access_key_id or "").strip()

    print("=== BOS 配置检查 ===")
    print(f"已配置: {bos_is_configured(s)}")
    print(f"BOS_BUCKET          = {bucket or '(空)'}")
    cname = bool(getattr(s, "bos_cname_enabled", False))
    backup = (getattr(s, "bos_backup_endpoint", "") or "").strip()
    path_style = bool(getattr(s, "bos_path_style_enable", True))
    read_exp = int(getattr(s, "bos_presign_read_expires_seconds", 3600))
    print(f"BOS_ENDPOINT        = {endpoint or '(空)'}")
    print(f"BOS_CNAME_ENABLED   = {cname}")
    print(f"BOS_PATH_STYLE_ENABLE = {path_style}")
    print(f"BOS_BACKUP_ENDPOINT = {backup or '(空)'}")
    print(f"BOS_PRESIGN_READ_EXPIRES_SECONDS = {read_exp}")
    print(f"BOS_PUBLIC_BASE_URL = {public_base or '(空)'}")
    print(f"BOS_ACCESS_KEY_ID   = {ak[:6]}...{ak[-4:] if len(ak) > 10 else ''}" if ak else "BOS_ACCESS_KEY_ID   = (空)")

    if not bos_is_configured(s):
        print("\n❌ 缺少 BOS 环境变量，请补全 /opt/wander_meet/.env")
        return 1

    if bucket.startswith("http") or ".bcebos.com" in bucket:
        print("\n❌ BOS_BUCKET 应只填 Bucket 名称（如 my-bucket），不要填完整 URL")
        return 1

    if public_base and not public_base.startswith("http"):
        print("\n❌ BOS_PUBLIC_BASE_URL 应以 https:// 开头")
        return 1

    if endpoint and ".cdn.bcebos.com" in endpoint and not cname:
        print(
            "\n⚠️  BOS_ENDPOINT 像是 CDN/自定义域名，上传应使用区域 endpoint（如 https://bd.bcebos.com），"
            "读/CDN 请配 BOS_PUBLIC_BASE_URL + BOS_CNAME_ENABLED=true"
        )

    try:
        from baidubce.services.bos.bos_client import BosClient
    except ImportError:
        print("\n❌ 未安装 bce-python-sdk，请 pip install -r requirements.txt")
        return 1

    upload_cfg = build_bce_upload_configuration(s)
    upload_client = BosClient(upload_cfg)
    read_cfg = build_bce_read_configuration(s)
    _ = BosClient(read_cfg)  # 仅验证读 client 可构建

    print("\n--- 当前 AK 可见的 Bucket 列表（上传 client） ---")
    try:
        resp = upload_client.list_buckets()
        names = [b.name for b in (resp.buckets or [])]
        if not names:
            print("(无 Bucket，请先在控制台创建)")
        else:
            for name in names:
                mark = "  ← 与 BOS_BUCKET 一致" if name == bucket else ""
                print(f"  - {name}{mark}")
    except Exception as exc:
        print(f"❌ list_buckets 失败: {exc}")
        return 1

    print(f"\n--- 探测 BOS_BUCKET={bucket!r} @ {endpoint}（上传） ---")
    try:
        upload_client.head_bucket(bucket)
        print("✅ head_bucket 成功，Bucket 存在且 AK 可访问")
    except Exception as exc:
        err = str(exc)
        print(f"❌ head_bucket 失败: {err}")
        if "does not exist" in err.lower() or "nosuchbucket" in err.lower():
            print(
                "\n常见原因:\n"
                "  1. BOS_BUCKET 名称与控制台不一致（区分大小写）\n"
                "  2. BOS_ENDPOINT 区域不对（上传用 bd.bcebos.com 等区域域名）\n"
                "  3. AK/SK 属于另一个百度云账号\n"
                "请到 控制台 → 对象存储 BOS → Bucket 列表 核对名称与区域。"
            )
        return 1

    read_endpoint = getattr(read_cfg, "endpoint", endpoint)
    print(f"\n--- 读/预签名 client endpoint = {read_endpoint} ---")
    print("✅ 读 client 配置已构建（GET 预签名走 CDN 时依赖 BOS_CNAME_ENABLED）")

    print("\n✅ 配置看起来正常，可再试上传头像")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
