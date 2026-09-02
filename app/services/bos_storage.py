"""百度 BOS 对象存储（头像、聊天图片等用户资源）。"""
from __future__ import annotations

import logging
import re
import time
import uuid
from functools import lru_cache

from fastapi import HTTPException

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_ALLOWED_EXT = frozenset({"jpg", "jpeg", "png", "webp"})
_EXT_TO_CONTENT_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class BosNotConfiguredError(RuntimeError):
    pass


def bos_is_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(
        (s.bos_access_key_id or "").strip()
        and (s.bos_secret_access_key or "").strip()
        and (s.bos_bucket or "").strip()
        and (s.bos_endpoint or "").strip()
        and (s.bos_public_base_url or "").strip()
    )


def _require_bos(settings: Settings | None = None) -> Settings:
    s = settings or get_settings()
    if not bos_is_configured(s):
        raise BosNotConfiguredError(
            "BOS 未配置：请设置 BOS_ACCESS_KEY_ID、BOS_SECRET_ACCESS_KEY、"
            "BOS_BUCKET、BOS_ENDPOINT、BOS_PUBLIC_BASE_URL"
        )
    return s


_REGIONAL_BOS_ENDPOINT = re.compile(r"^https?://[a-z]{2}\.bcebos\.com/?$", re.I)


def _is_regional_bos_endpoint(endpoint: str) -> bool:
    return bool(_REGIONAL_BOS_ENDPOINT.match((endpoint or "").strip()))


def _read_bos_endpoint(s: Settings) -> str:
    """读/预签名用的 endpoint：自定义域名时取 BOS_PUBLIC_BASE_URL。"""
    if s.bos_cname_enabled:
        base = (s.bos_public_base_url or "").strip().rstrip("/")
        if base.startswith("http"):
            return base
    return s.bos_endpoint.strip()


def build_bce_upload_configuration(settings: Settings | None = None):
    """上传写 BOS：endpoint 取 ``BOS_ENDPOINT``。

    - 区域域名（如 ``https://bd.bcebos.com``）：``cname_enabled=false``（方式 A）。
    - CDN/自定义域名：须 ``BOS_CNAME_ENABLED=true``，并建议配 ``BOS_PATH_STYLE_ENABLE``、
      ``BOS_BACKUP_ENDPOINT``（方式 B）。
    """
    from baidubce.auth.bce_credentials import BceCredentials
    from baidubce.bce_client_configuration import BceClientConfiguration

    s = _require_bos(settings)
    endpoint = s.bos_endpoint.strip()
    use_cname = bool(s.bos_cname_enabled and not _is_regional_bos_endpoint(endpoint))
    kwargs: dict = {
        "credentials": BceCredentials(
            s.bos_access_key_id.strip(),
            s.bos_secret_access_key.strip(),
        ),
        "endpoint": endpoint,
        "cname_enabled": use_cname,
    }
    if use_cname and s.bos_path_style_enable:
        kwargs["path_style_enable"] = True
    backup = (s.bos_backup_endpoint or "").strip()
    if backup:
        kwargs["backup_endpoint"] = backup
    return BceClientConfiguration(**kwargs)


def build_bce_read_configuration(settings: Settings | None = None):
    """读 BOS / 生成 GET 预签名：可走自定义 CDN 域名 + cname。"""
    from baidubce.auth.bce_credentials import BceCredentials
    from baidubce.bce_client_configuration import BceClientConfiguration

    s = _require_bos(settings)
    endpoint = _read_bos_endpoint(s)
    use_cname = bool(s.bos_cname_enabled and not _is_regional_bos_endpoint(endpoint))
    kwargs: dict = {
        "credentials": BceCredentials(
            s.bos_access_key_id.strip(),
            s.bos_secret_access_key.strip(),
        ),
        "endpoint": endpoint,
        "cname_enabled": use_cname,
    }
    if use_cname and s.bos_path_style_enable:
        kwargs["path_style_enable"] = True
    backup = (s.bos_backup_endpoint or "").strip()
    if backup:
        kwargs["backup_endpoint"] = backup
    return BceClientConfiguration(**kwargs)


def build_bce_client_configuration(settings: Settings | None = None):
    """兼容旧调用：默认返回上传用配置。"""
    return build_bce_upload_configuration(settings)


@lru_cache(maxsize=1)
def _bos_upload_client():
    from baidubce.services.bos.bos_client import BosClient

    return BosClient(build_bce_upload_configuration())


@lru_cache(maxsize=1)
def _bos_read_client():
    from baidubce.services.bos.bos_client import BosClient

    return BosClient(build_bce_read_configuration())


def normalize_image_ext(
    file_ext: str | None, content_type: str | None = None, *, kind: str = "图片"
) -> str:
    ext = (file_ext or "").strip().lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext in _ALLOWED_EXT:
        return "jpg" if ext == "jpeg" else ext
    ct = (content_type or "").split(";")[0].strip().lower()
    mapped = _CONTENT_TYPE_TO_EXT.get(ct)
    if mapped:
        return mapped
    raise HTTPException(status_code=400, detail=f"仅支持 jpg、png、webp {kind}")


def normalize_avatar_ext(file_ext: str | None, content_type: str | None = None) -> str:
    return normalize_image_ext(file_ext, content_type, kind="头像")


def avatar_object_key(user_id: int, ext: str) -> str:
    safe_ext = normalize_avatar_ext(ext)
    return f"wm/avatar/u_{user_id}/avatar.{safe_ext}"


def chat_image_object_key(user_id: int, ext: str) -> str:
    safe_ext = normalize_image_ext(ext)
    return f"wm/chat/u_{user_id}/{uuid.uuid4().hex}.{safe_ext}"


def photo_verify_object_key(user_id: int, ext: str) -> str:
    safe_ext = normalize_image_ext(ext)
    return f"wm/photo_verify/u_{user_id}/selfie.{safe_ext}"


def feed_image_object_key(user_id: int, ext: str) -> str:
    safe_ext = normalize_image_ext(ext)
    return f"wm/feed/u_{user_id}/{uuid.uuid4().hex}.{safe_ext}"


def activity_image_object_key(user_id: int, ext: str) -> str:
    safe_ext = normalize_image_ext(ext)
    return f"wm/activity/u_{user_id}/{uuid.uuid4().hex}.{safe_ext}"


def public_url_for_object_key(object_key: str, settings: Settings | None = None) -> str:
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    key = object_key.lstrip("/")
    return f"{base}/{key}"


def parse_bos_object_key(stored: str | None, settings: Settings | None = None) -> str | None:
    """从 DB 存储的 object key 或历史公网 URL 解析 BOS 对象名（如 wm/avatar/...）。"""
    if not stored:
        return None
    raw = str(stored).strip()
    if not raw:
        return None
    path_only = raw.split("?", 1)[0].strip()
    if path_only.startswith("wm/"):
        return path_only.lstrip("/")
    if path_only.startswith("/wm/"):
        return path_only.lstrip("/")
    try:
        s = _require_bos(settings)
    except BosNotConfiguredError:
        return None
    base = s.bos_public_base_url.rstrip("/")
    prefix = base + "/"
    if path_only.startswith(prefix):
        key = path_only[len(prefix) :].lstrip("/")
        return key if key.startswith("wm/") else None
    return None


def create_presigned_get_url(object_key: str, settings: Settings | None = None) -> str:
    """按 bos_test 方式生成 GET 预签名 URL（仅 object 名不同）。"""
    s = _require_bos(settings)
    key = object_key.lstrip("/")
    bucket = s.bos_bucket.strip()
    try:
        client = _bos_read_client()
        url = client.generate_pre_signed_url(
            bucket,
            key,
            expiration_in_seconds=s.bos_presign_read_expires_seconds,
        )
    except Exception as exc:
        logger.exception("BOS presign GET failed key=%s", key)
        raise HTTPException(status_code=502, detail="生成图片访问链接失败") from exc
    if isinstance(url, bytes):
        url = url.decode("utf-8")
    return str(url)


def resolve_bos_read_url(stored: str | None, settings: Settings | None = None) -> str | None:
    """对外读 BOS 对象：返回预签名 GET URL；非本 bucket 对象原样返回。"""
    if not stored:
        return None
    key = parse_bos_object_key(stored, settings)
    if not key:
        return stored.strip() or None
    return create_presigned_get_url(key, settings)


def resolve_bos_read_urls(
    urls: list[str] | None, settings: Settings | None = None
) -> list[str] | None:
    if urls is None:
        return None
    if not urls:
        return []
    return [resolve_bos_read_url(u, settings) or u for u in urls]


def validate_stored_avatar_url(url: str | None, settings: Settings | None = None) -> str | None:
    if url is None:
        return None
    u = url.strip()
    if not u:
        return None
    if len(u) > 512:
        raise HTTPException(status_code=400, detail="avatarUrl too long")
    key = parse_bos_object_key(u, settings)
    if key and re.match(r"^wm/avatar/u_\d+/avatar\.(jpg|jpeg|png|webp)$", key):
        return u if u.startswith("http") else public_url_for_object_key(key, settings)
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    if not path_url.startswith(base + "/"):
        raise HTTPException(status_code=400, detail="avatarUrl must use configured BOS public base")
    if not re.match(r"^https?://", u.split("?", 1)[0]):
        raise HTTPException(status_code=400, detail="avatarUrl must be http(s) URL")
    legacy_key = parse_bos_object_key(path_url, settings)
    if legacy_key:
        return u
    raise HTTPException(status_code=400, detail="avatarUrl invalid")


def validate_stored_feed_image_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u or len(u) > 512:
        raise HTTPException(status_code=400, detail="imageUrl invalid")
    key = parse_bos_object_key(u, settings)
    if key:
        for prefix in (f"wm/feed/u_{user_id}/", f"wm/chat/u_{user_id}/"):
            if key.startswith(prefix):
                return u if u.startswith("http") else public_url_for_object_key(key, settings)
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    for prefix in (f"{base}/wm/feed/u_{user_id}/", f"{base}/wm/chat/u_{user_id}/"):
        if path_url.startswith(prefix) and re.match(r"^https?://", path_url):
            legacy = parse_bos_object_key(path_url, settings)
            if legacy:
                return u
    raise HTTPException(status_code=400, detail="imageUrl must be your uploaded feed image")


def validate_stored_activity_image_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u or len(u) > 512:
        raise HTTPException(status_code=400, detail="imageUrl invalid")
    key = parse_bos_object_key(u, settings)
    expected_prefix = f"wm/activity/u_{user_id}/"
    if key and key.startswith(expected_prefix):
        return u if u.startswith("http") else public_url_for_object_key(key, settings)
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    expected_url_prefix = f"{base}/wm/activity/u_{user_id}/"
    if path_url.startswith(expected_url_prefix) and re.match(r"^https?://", path_url):
        legacy = parse_bos_object_key(path_url, settings)
        if legacy:
            return u
    raise HTTPException(status_code=400, detail="imageUrl must be your uploaded activity image")


def validate_stored_chat_image_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u:
        raise HTTPException(status_code=400, detail="imageUrl is required")
    if len(u) > 512:
        raise HTTPException(status_code=400, detail="imageUrl too long")
    key = parse_bos_object_key(u, settings)
    expected_prefix = f"wm/chat/u_{user_id}/"
    if key and key.startswith(expected_prefix):
        return u if u.startswith("http") else public_url_for_object_key(key, settings)
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    expected_url_prefix = f"{base}/wm/chat/u_{user_id}/"
    if not path_url.startswith(expected_url_prefix):
        raise HTTPException(status_code=400, detail="imageUrl must be your uploaded chat image")
    if not re.match(r"^https?://", path_url):
        raise HTTPException(status_code=400, detail="imageUrl must be http(s) URL")
    legacy = parse_bos_object_key(path_url, settings)
    if legacy:
        return u
    raise HTTPException(status_code=400, detail="imageUrl must be your uploaded chat image")


def sniff_image_content_type(data: bytes) -> str | None:
    """通过魔数检测图片类型，替代已移除的 imghdr 模块"""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return None


def put_avatar_bytes(*, user_id: int, data: bytes, content_type: str, file_ext: str | None = None) -> str:
    s = _require_bos()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > s.bos_avatar_max_bytes:
        raise HTTPException(status_code=400, detail="avatar file too large")

    sniffed = sniff_image_content_type(data)
    if not sniffed:
        raise HTTPException(status_code=400, detail="invalid image file")

    ext = normalize_avatar_ext(file_ext, sniffed)
    ct = _EXT_TO_CONTENT_TYPE.get(ext, sniffed)
    key = avatar_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()

    try:
        from baidubce.services.bos import canned_acl

        client = _bos_upload_client()
        client.put_object_from_string(
            bucket,
            key,
            data,
            content_type=ct,
            user_headers={b"x-bce-acl": canned_acl.PUBLIC_READ},
        )
    except Exception as exc:
        logger.exception(
            "BOS put_object failed user_id=%s bucket=%s endpoint=%s key=%s",
            user_id,
            bucket,
            s.bos_endpoint.strip(),
            key,
        )
        detail = "头像上传存储失败"
        msg = str(exc)
        if "bucket does not exist" in msg.lower() or "nosuchbucket" in msg.lower():
            detail = (
                "BOS Bucket 不存在或与 Endpoint 区域不匹配，"
                "请检查 BOS_BUCKET、BOS_ENDPOINT 是否与控制台一致"
            )
        raise HTTPException(status_code=502, detail=detail) from exc

    public = public_url_for_object_key(key, s)
    return f"{public}?v={int(time.time())}"


def put_chat_image_bytes(*, user_id: int, data: bytes, content_type: str, file_ext: str | None = None) -> str:
    s = _require_bos()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > s.bos_chat_image_max_bytes:
        raise HTTPException(status_code=400, detail="chat image file too large")

    sniffed = sniff_image_content_type(data)
    if not sniffed:
        raise HTTPException(status_code=400, detail="invalid image file")

    ext = normalize_image_ext(file_ext, sniffed)
    ct = _EXT_TO_CONTENT_TYPE.get(ext, sniffed)
    key = chat_image_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()

    try:
        from baidubce.services.bos import canned_acl

        client = _bos_upload_client()
        client.put_object_from_string(
            bucket,
            key,
            data,
            content_type=ct,
            user_headers={b"x-bce-acl": canned_acl.PUBLIC_READ},
        )
    except Exception as exc:
        logger.exception(
            "BOS put_object failed user_id=%s bucket=%s endpoint=%s key=%s",
            user_id,
            bucket,
            s.bos_endpoint.strip(),
            key,
        )
        detail = "聊天图片上传存储失败"
        msg = str(exc)
        if "bucket does not exist" in msg.lower() or "nosuchbucket" in msg.lower():
            detail = (
                "BOS Bucket 不存在或与 Endpoint 区域不匹配，"
                "请检查 BOS_BUCKET、BOS_ENDPOINT 是否与控制台一致"
            )
        raise HTTPException(status_code=502, detail=detail) from exc

    public = public_url_for_object_key(key, s)
    return f"{public}?v={int(time.time())}"


def put_feed_image_bytes(
    *, user_id: int, data: bytes, content_type: str, file_ext: str | None = None
) -> str:
    s = _require_bos()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    max_bytes = getattr(s, "bos_feed_image_max_bytes", 8 * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="photo file too large")
    sniffed = sniff_image_content_type(data)
    if not sniffed:
        raise HTTPException(status_code=400, detail="invalid image file")
    ext = normalize_image_ext(file_ext, sniffed)
    ct = _EXT_TO_CONTENT_TYPE.get(ext, sniffed)
    key = feed_image_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()
    try:
        from baidubce.services.bos import canned_acl

        client = _bos_upload_client()
        client.put_object_from_string(
            bucket,
            key,
            data,
            content_type=ct,
            user_headers={b"x-bce-acl": canned_acl.PUBLIC_READ},
        )
    except Exception as exc:
        logger.exception("BOS feed image upload failed user_id=%s", user_id)
        raise HTTPException(status_code=502, detail="动态图片上传失败") from exc
    return public_url_for_object_key(key, s) + f"?v={int(time.time())}"


def put_activity_image_bytes(
    *, user_id: int, data: bytes, content_type: str, file_ext: str | None = None
) -> str:
    s = _require_bos()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    max_bytes = getattr(s, "bos_activity_image_max_bytes", 8 * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="photo file too large")
    sniffed = sniff_image_content_type(data)
    if not sniffed:
        raise HTTPException(status_code=400, detail="invalid image file")
    ext = normalize_image_ext(file_ext, sniffed)
    ct = _EXT_TO_CONTENT_TYPE.get(ext, sniffed)
    key = activity_image_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()
    try:
        from baidubce.services.bos import canned_acl

        client = _bos_upload_client()
        client.put_object_from_string(
            bucket,
            key,
            data,
            content_type=ct,
            user_headers={b"x-bce-acl": canned_acl.PUBLIC_READ},
        )
    except Exception as exc:
        logger.exception("BOS activity image upload failed user_id=%s", user_id)
        raise HTTPException(status_code=502, detail="活动图片上传失败") from exc
    return public_url_for_object_key(key, s) + f"?v={int(time.time())}"


def validate_stored_photo_selfie_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u or len(u) > 512:
        raise HTTPException(status_code=400, detail="selfieUrl invalid")
    key = parse_bos_object_key(u, settings)
    if key:
        for prefix in (f"wm/photo_verify/u_{user_id}/", f"wm/chat/u_{user_id}/"):
            if key.startswith(prefix):
                return u if u.startswith("http") else public_url_for_object_key(key, settings)
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    for prefix in (f"{base}/wm/photo_verify/u_{user_id}/", f"{base}/wm/chat/u_{user_id}/"):
        if path_url.startswith(prefix):
            legacy = parse_bos_object_key(path_url, settings)
            if legacy:
                return u
    raise HTTPException(status_code=400, detail="selfieUrl must be your uploaded photo")


def put_photo_verify_bytes(
    *, user_id: int, data: bytes, content_type: str, file_ext: str | None = None
) -> str:
    s = _require_bos()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    max_bytes = getattr(s, "bos_photo_verify_max_bytes", 8 * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="photo file too large")
    sniffed = sniff_image_content_type(data)
    if not sniffed:
        raise HTTPException(status_code=400, detail="invalid image file")
    ext = normalize_image_ext(file_ext, sniffed)
    ct = _EXT_TO_CONTENT_TYPE.get(ext, sniffed)
    key = photo_verify_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()
    try:
        from baidubce.services.bos import canned_acl

        client = _bos_upload_client()
        client.put_object_from_string(
            bucket,
            key,
            data,
            content_type=ct,
            user_headers={b"x-bce-acl": canned_acl.PUBLIC_READ},
        )
    except Exception as exc:
        logger.exception("BOS photo verify upload failed user_id=%s", user_id)
        raise HTTPException(status_code=502, detail="自拍上传存储失败") from exc
    return public_url_for_object_key(key, s) + f"?v={int(time.time())}"


def create_avatar_presigned_put_url(*, user_id: int, file_ext: str) -> dict[str, str]:
    """预签名 PUT（仅签 host，客户端 PUT 时不要额外加 Content-Type 头）。"""
    from baidubce.http import http_methods

    s = _require_bos()
    ext = normalize_avatar_ext(file_ext)
    key = avatar_object_key(user_id, ext)
    bucket = s.bos_bucket.strip()
    try:
        client = _bos_upload_client()
        upload_url = client.generate_pre_signed_url(
            bucket,
            key,
            expiration_in_seconds=s.bos_presign_expires_seconds,
            httpmethod=http_methods.PUT,
        )
    except Exception as exc:
        logger.exception("BOS presign failed user_id=%s key=%s", user_id, key)
        raise HTTPException(status_code=502, detail="生成上传凭证失败") from exc

    if isinstance(upload_url, bytes):
        upload_url = upload_url.decode("utf-8")

    public_url = create_presigned_get_url(key, s)
    return {
        "uploadUrl": upload_url,
        "objectKey": key,
        "publicUrl": public_url,
        "headers": {},
    }
