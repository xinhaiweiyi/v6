from datetime import timedelta
from random import randint

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone


_memory_store = {}


def _code_key(email):
    return f"register:code:{email.lower()}"


def _cooldown_key(email):
    return f"register:cooldown:{email.lower()}"


def _memory_get(key):
    item = _memory_store.get(key)
    if not item:
        return None
    value, expires_at = item
    if expires_at <= timezone.now():
        _memory_store.pop(key, None)
        return None
    return value


def _memory_set(key, value, timeout):
    _memory_store[key] = (value, timezone.now() + timedelta(seconds=timeout))


def send_verification_code(email):
    cooldown_key = _cooldown_key(email)
    try:
        cooldown_exists = cache.get(cooldown_key)
    except Exception:
        cooldown_exists = _memory_get(cooldown_key)

    if cooldown_exists:
        return False, f"验证码已发送，请在 {settings.VERIFICATION_CODE_RESEND_SECONDS} 秒后重试。"

    code = f"{randint(100000, 999999)}"
    try:
        cache.set(_code_key(email), code, timeout=settings.VERIFICATION_CODE_EXPIRE_SECONDS)
        cache.set(cooldown_key, "1", timeout=settings.VERIFICATION_CODE_RESEND_SECONDS)
    except Exception:
        _memory_set(_code_key(email), code, settings.VERIFICATION_CODE_EXPIRE_SECONDS)
        _memory_set(cooldown_key, "1", settings.VERIFICATION_CODE_RESEND_SECONDS)

    try:
        send_mail(
            subject="在线视频学习系统注册验证码",
            message=f"您的验证码是：{code}，{settings.VERIFICATION_CODE_EXPIRE_SECONDS // 60} 分钟内有效。",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        return True, f"邮件发送失败，已切换为开发模式验证码：{code}"
    return True, "验证码已发送，请前往邮箱查收。"


def verify_code(email, code):
    try:
        stored_code = cache.get(_code_key(email))
    except Exception:
        stored_code = _memory_get(_code_key(email))
    if stored_code and stored_code == code:
        try:
            cache.delete(_code_key(email))
        except Exception:
            _memory_store.pop(_code_key(email), None)
        return True
    return False
