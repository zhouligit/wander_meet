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
        from app.services.bos_storage import bos_is_configured
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
    print(f"BOS_ENDPOINT        = {endpoint or '(空)'}")
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

    try:
        from baidubce.auth.bce_credentials import BceCredentials
        from baidubce.bce_client_configuration import BceClientConfiguration
        from baidubce.services.bos.bos_client import BosClient
    except ImportError:
        print("\n❌ 未安装 bce-python-sdk，请 pip install -r requirements.txt")
        return 1

    cfg = BceClientConfiguration(
        credentials=BceCredentials(s.bos_access_key_id.strip(), s.bos_secret_access_key.strip()),
        endpoint=endpoint,
    )
    client = BosClient(cfg)

    print("\n--- 当前 AK 可见的 Bucket 列表 ---")
    try:
        resp = client.list_buckets()
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

    print(f"\n--- 探测 BOS_BUCKET={bucket!r} @ {endpoint} ---")
    try:
        client.head_bucket(bucket)
        print("✅ head_bucket 成功，Bucket 存在且 AK 可访问")
    except Exception as exc:
        err = str(exc)
        print(f"❌ head_bucket 失败: {err}")
        if "does not exist" in err.lower() or "nosuchbucket" in err.lower():
            print(
                "\n常见原因:\n"
                "  1. BOS_BUCKET 名称与控制台不一致（区分大小写）\n"
                "  2. BOS_ENDPOINT 区域不对（如 Bucket 在广州却填 bj.bcebos.com）\n"
                "  3. AK/SK 属于另一个百度云账号\n"
                "请到 控制台 → 对象存储 BOS → Bucket 列表 核对名称与区域。"
            )
        return 1

    print("\n✅ 配置看起来正常，可再试上传头像")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
