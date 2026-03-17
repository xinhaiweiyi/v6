from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("邮箱不能为空。")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.STUDENT)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("超级管理员必须具有 is_staff=True。")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("超级管理员必须具有 is_superuser=True。")
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "学生"
        TEACHER = "teacher", "老师"
        ADMIN = "admin", "管理员"

    email = models.EmailField("邮箱", unique=True)
    username = models.CharField("用户名", max_length=150)
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.STUDENT)
    avatar = models.FileField("头像", upload_to="avatars/", blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    is_staff = models.BooleanField("后台权限", default=False)
    date_joined = models.DateTimeField("加入时间", default=timezone.now)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return f"{self.username}({self.get_role_display()})"

    @property
    def display_name(self):
        return self.username if self.is_active else "已注销用户"
