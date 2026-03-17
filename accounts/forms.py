from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from accounts.models import User
from accounts.services import verify_code


def apply_control_style(field, textarea=False):
    if isinstance(field.widget, forms.Select):
        field.widget.attrs.setdefault(
            "class",
            "select select-bordered h-11 w-full rounded-lg border-slate-200 bg-white",
        )
        return
    base_class = (
        "textarea textarea-bordered min-h-[120px] w-full rounded-lg border-slate-200 bg-white"
        if textarea
        else "input input-bordered h-11 w-full rounded-lg border-slate-200 bg-white"
    )
    field.widget.attrs.setdefault("class", base_class)


class SendCodeForm(forms.Form):
    email = forms.EmailField(label="邮箱")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("该邮箱已注册，请直接登录。")
        return email


class RegistrationForm(forms.Form):
    role = forms.ChoiceField(
        label="身份",
        choices=[
            (User.Role.STUDENT, User.Role.STUDENT.label),
            (User.Role.TEACHER, User.Role.TEACHER.label),
        ],
    )
    username = forms.CharField(label="用户名", max_length=150)
    email = forms.EmailField(label="邮箱")
    code = forms.CharField(label="验证码", max_length=6)
    password1 = forms.CharField(label="密码", widget=forms.PasswordInput)
    password2 = forms.CharField(label="确认密码", widget=forms.PasswordInput)

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role == User.Role.ADMIN:
            raise forms.ValidationError("管理员账号只能由后台创建。")
        return role

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("该邮箱已注册。")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        email = cleaned_data.get("email")
        code = cleaned_data.get("code")
        username = cleaned_data.get("username")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "两次输入的密码不一致。")
        if password1:
            temp_user = User(email=email or "", username=username or "临时用户")
            validate_password(password1, user=temp_user)
        if email and code and not verify_code(email, code):
            self.add_error("code", "验证码错误或已过期。")
        return cleaned_data

    def save(self):
        return User.objects.create_user(
            email=self.cleaned_data["email"],
            username=self.cleaned_data["username"],
            password=self.cleaned_data["password1"],
            role=self.cleaned_data["role"],
        )


class LoginForm(forms.Form):
    email = forms.EmailField(label="邮箱")
    password = forms.CharField(label="密码", widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            apply_control_style(field)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email.lower(),
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError("邮箱或密码错误。")
            if not self.user_cache.is_active:
                raise forms.ValidationError("该账号已被注销，无法登录。")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_style(self.fields["username"])
        self.fields["avatar"].widget.attrs.setdefault(
            "class",
            "file-input file-input-bordered w-full rounded-lg border-slate-200 bg-white",
        )

    class Meta:
        model = User
        fields = ["username", "avatar"]
        labels = {"username": "用户名", "avatar": "头像"}


class PasswordUpdateForm(forms.Form):
    old_password = forms.CharField(label="原密码", widget=forms.PasswordInput)
    new_password1 = forms.CharField(label="新密码", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="确认新密码", widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            apply_control_style(field)

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError("原密码不正确。")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "两次输入的密码不一致。")
        if password1:
            validate_password(password1, user=self.user)
        return cleaned_data


for _field in SendCodeForm.base_fields.values():
    apply_control_style(_field)

for _field in RegistrationForm.base_fields.values():
    apply_control_style(_field)
