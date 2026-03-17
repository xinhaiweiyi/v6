from django import template


register = template.Library()


@register.filter
def status_badge(status):
    mapping = {
        "draft": "badge-neutral",
        "pending": "badge-warning",
        "published": "badge-success",
        "rejected": "badge-error",
        "offline": "badge-info",
    }
    return mapping.get(status, "badge-neutral")


@register.filter
def role_badge(role):
    mapping = {
        "student": "badge-info",
        "teacher": "badge-primary",
        "admin": "badge-success",
    }
    return mapping.get(role, "badge-neutral")


@register.filter
def duration_human(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "00:00"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"
