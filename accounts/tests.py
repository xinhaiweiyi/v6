from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from accounts.models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class AccountFlowTests(TestCase):
    def test_register_form_does_not_offer_admin_role(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="admin"')
        self.assertContains(response, 'data-cooldown-seconds="60"')
        self.assertContains(response, 'id="send-code-status"')

    def test_send_code_and_register_student(self):
        response = self.client.post(reverse("accounts:send-code"), {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        code = cache.get("register:code:student@example.com")

        register_response = self.client.post(
            reverse("accounts:register"),
            {
                "role": "student",
                "username": "测试学生",
                "email": "student@example.com",
                "code": code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(register_response, reverse("learning:student-dashboard"))
        self.assertTrue(User.objects.filter(email="student@example.com", role="student").exists())

    @patch("accounts.services.send_mail", side_effect=RuntimeError("smtp error"))
    def test_send_code_failure_only_shows_mail_error(self, _mock_send_mail):
        response = self.client.post(reverse("accounts:send-code"), {"email": "student-fail@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True, "message": "邮件发送失败"})

    def test_admin_cannot_register_from_frontend(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "role": "admin",
                "username": "管理员",
                "email": "admin@example.com",
                "code": "123456",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="admin@example.com", role="admin").exists())

    def test_profile_page_shows_avatar_preview_without_clear_checkbox(self):
        user = User.objects.create_user(
            email="profile@example.com",
            username="ProfileUser",
            password="StrongPass123!",
        )
        user.avatar = SimpleUploadedFile("avatar.jpg", b"avatar-image", content_type="image/jpeg")
        user.save(update_fields=["avatar", "updated_at"])
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, user.avatar.url)
        self.assertContains(response, 'id="avatar-preview"')
        self.assertContains(response, 'accept="image/*"')
        self.assertNotContains(response, "清除")
        self.assertNotContains(response, "Currently")

    def test_profile_page_uses_image_file_input_without_default_clear_control(self):
        user = User.objects.create_user(
            email="profile2@example.com",
            username="ProfileUser2",
            password="StrongPass123!",
        )
        user.avatar = SimpleUploadedFile("avatar2.jpg", b"avatar-image-2", content_type="image/jpeg")
        user.save(update_fields=["avatar", "updated_at"])
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="file"')
        self.assertNotContains(response, 'name="avatar-clear"')

    def test_profile_password_mismatch_shows_error_message(self):
        user = User.objects.create_user(
            email="password-mismatch@example.com",
            username="PasswordUser",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:profile"),
            {
                "action": "password",
                "password-old_password": "StrongPass123!",
                "password-new_password1": "NewStrongPass123!",
                "password-new_password2": "DifferentStrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "密码修改失败，请检查输入。")
        self.assertContains(response, "两次输入的密码不一致")
