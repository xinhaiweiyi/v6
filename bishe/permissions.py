from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse


def role_home_url(user):
    if user.role == "student":
        return reverse("learning:student-dashboard")
    if user.role == "teacher":
        return reverse("portal:teacher-dashboard")
    return reverse("admin_panel:admin-dashboard")


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("您没有访问该页面的权限。")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def anonymous_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(role_home_url(request.user))
        return view_func(request, *args, **kwargs)

    return wrapped
