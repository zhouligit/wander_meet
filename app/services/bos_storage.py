"""百度 BOS 对象存储（头像、聊天图片等用户资源）。"""
from __future__ import annotations

import imghdr
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


def build_bce_client_configuration(settings: Settings | None = None):
    """构造 BOS SDK 配置（支持自定义域名 cname_enabled + backup_endpoint）。"""
    from baidubce.auth.bce_credentials import BceCredentials
    from baidubce.bce_client_configuration import BceClientConfiguration

    s = _require_bos(settings)
    kwargs: dict = {
        "credentials": BceCredentials(
            s.bos_access_key_id.strip(),
            s.bos_secret_access_key.strip(),
        ),
        "endpoint": s.bos_endpoint.strip(),
    }
    if s.bos_cname_enabled:
        kwargs["cname_enabled"] = True
    backup = (s.bos_backup_endpoint or "").strip()
    if backup:
        kwargs["backup_endpoint"] = backup
    return BceClientConfiguration(**kwargs)


@lru_cache(maxsize=1)
def _bos_client():
    from baidubce.services.bos.bos_client import BosClient

    return BosClient(build_bce_client_configuration())


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


def validate_stored_avatar_url(url: str | None, settings: Settings | None = None) -> str | None:
    if url is None:
        return None
    u = url.strip()
    if not u:
        return None
    if len(u) > 512:
        raise HTTPException(status_code=400, detail="avatarUrl too long")
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    if not path_url.startswith(base + "/"):
        raise HTTPException(status_code=400, detail="avatarUrl must use configured BOS public base")
    if not re.match(r"^https?://", u):
        raise HTTPException(status_code=400, detail="avatarUrl must be http(s) URL")
    return u


def validate_stored_feed_image_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u or len(u) > 512:
        raise HTTPException(status_code=400, detail="imageUrl invalid")
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    for prefix in (f"{base}/wm/feed/u_{user_id}/", f"{base}/wm/chat/u_{user_id}/"):
        if path_url.startswith(prefix) and re.match(r"^https?://", u):
            return u
    raise HTTPException(status_code=400, detail="imageUrl must be your uploaded feed image")


def validate_stored_activity_image_url(
    url: str, user_id: int, settings: Settings | None = None
) -> str:
    u = url.strip()
    if not u or len(u) > 512:
        raise HTTPException(status_code=400, detail="imageUrl invalid")
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    expected_prefix = f"{base}/wm/activity/u_{user_id}/"
    if path_url.startswith(expected_prefix) and re.match(r"^https?://", u):
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
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    expected_prefix = f"{base}/wm/chat/u_{user_id}/"
    if not path_url.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="imageUrl must be your uploaded chat image")
    if not re.match(r"^https?://", u):
        raise HTTPException(status_code=400, detail="imageUrl must be http(s) URL")
    return u


def sniff_image_content_type(data: bytes) -> str | None:
    kind = imghdr.what(None, h=data[:512])
    if kind == "jpeg":
        return "image/jpeg"
    if kind == "png":
        return "image/png"
    if kind == "webp":
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

        client = _bos_client()
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
    # 同一路径覆盖上传时，小程序 <image> 会强缓存旧图，必须带版本参数
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

        client = _bos_client()
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

        client = _bos_client()
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

        client = _bos_client()
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
    s = _require_bos(settings)
    base = s.bos_public_base_url.rstrip("/")
    path_url = u.split("?", 1)[0]
    for prefix in (f"{base}/wm/photo_verify/u_{user_id}/", f"{base}/wm/chat/u_{user_id}/"):
        if path_url.startswith(prefix):
            if re.match(r"^https?://", u):
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

        client = _bos_client()
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
        client = _bos_client()
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

    public_url = public_url_for_object_key(key, s)
    return {
        "uploadUrl": upload_url,
        "objectKey": key,
        "publicUrl": public_url,
        "headers": {},
    }
