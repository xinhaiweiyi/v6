from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.forms import (
    LoginForm,
    PasswordUpdateForm,
    ProfileForm,
    RegistrationForm,
    SendCodeForm,
)
from accounts.services import send_verification_code
from bishe.permissions import anonymous_required, role_home_url


@anonymous_required
@require_http_methods(["GET", "POST"])
def login_view(request):
    form = LoginForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, "登录成功，欢迎回来。")
        return redirect(role_home_url(user))
    return render(request, "auth/login.html", {"form": form})


@anonymous_required
@require_http_methods(["GET", "POST"])
def register_view(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "注册成功，已为您自动登录。")
        return redirect(role_home_url(user))
    return render(
        request,
        "auth/register.html",
        {
            "form": form,
            "code_resend_seconds": settings.VERIFICATION_CODE_RESEND_SECONDS,
        },
    )


@require_POST
def send_code_view(request):
    form = SendCodeForm(request.POST)
    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
        return JsonResponse({"ok": False, "message": error}, status=400)
    success, message = send_verification_code(form.cleaned_data["email"])
    status = 200 if success else 429
    return JsonResponse({"ok": success, "message": message}, status=status)


@require_http_methods(["GET", "POST"])
def profile_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    password_form = PasswordUpdateForm(request.user, request.POST or None, prefix="password")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile" and profile_form.is_valid():
            profile_form.save()
            messages.success(request, "账号信息已更新。")
            return redirect("accounts:profile")
        if action == "password" and password_form.is_valid():
            request.user.set_password(password_form.cleaned_data["new_password1"])
            request.user.save(update_fields=["password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "密码修改成功。")
            return redirect("accounts:profile")

    return render(
        request,
        "auth/profile.html",
        {
            "profile_form": profile_form,
            "password_form": password_form,
        },
    )


def logout_view(request):
    logout(request)
    messages.success(request, "您已安全退出登录。")
    return redirect("portal:home")
