from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

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
