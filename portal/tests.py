from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Category, Chapter, Course, Lesson
from learning.models import Comment


class PortalRedirectTests(TestCase):
    def test_role_home_redirects_by_role(self):
        student = User.objects.create_user(
            email="student@example.com",
            username="学生",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        self.client.force_login(student)
        response = self.client.get(reverse("portal:role-home"))
        self.assertRedirects(response, reverse("learning:student-dashboard"))


class TeacherDashboardTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher-dashboard@example.com",
            username="教师工作台",
            password="StrongPass123!",
            role=User.Role.TEACHER,
        )
        self.category = Category.objects.create(name="Teacher Dashboard Category", is_active=True)
        self.pending_course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="待审核课程",
            description="待审核",
            status=Course.Status.PENDING,
        )
        self.published_course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="已发布课程",
            description="已发布",
            status=Course.Status.PUBLISHED,
        )
        chapter = Chapter.objects.create(course=self.published_course, title="第一章", order=1)
        self.lesson = Lesson.objects.create(
            chapter=chapter,
            title="第一节",
            order=1,
            duration_seconds=120,
            video="course_videos/test.mp4",
        )
        self.student = User.objects.create_user(
            email="teacher-dashboard-student@example.com",
            username="学生A",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        Comment.objects.create(
            course=self.published_course,
            lesson=self.lesson,
            user=self.student,
            content="老师你好",
        )

    def test_teacher_dashboard_shows_latest_comments_only(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("portal:teacher-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "课程总数")
        self.assertNotContains(response, "待审核课程")
        self.assertNotContains(response, "评论数")
        self.assertContains(response, "最新评论")
        self.assertContains(response, self.published_course.title)
        self.assertContains(response, "老师你好")
        self.assertNotIn("stats", response.context)
        self.assertEqual(len(response.context["comments"]), 1)


class AdminCourseReviewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            username="管理员",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            username="老师",
            password="StrongPass123!",
            role=User.Role.TEACHER,
        )
        self.category = Category.objects.create(name="IT", is_active=True)
        self.published_course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="已发布课程",
            description="课程描述",
            status=Course.Status.PUBLISHED,
        )

    def test_admin_course_review_defaults_to_all_statuses(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:courses"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.published_course.title)

    def test_admin_user_list_is_paginated(self):
        for index in range(12):
            User.objects.create_user(
                email=f"student{index}@example.com",
                username=f"Student {index}",
                password="StrongPass123!",
                role=User.Role.STUDENT,
            )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:users"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertContains(response, "上一页")

    def test_admin_can_update_course_category_from_review_list(self):
        new_category = Category.objects.create(name="Design", is_active=True)
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin_panel:course-update-category", args=[self.published_course.id]),
            {"category": new_category.id, "next": reverse("admin_panel:courses")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.published_course.refresh_from_db()
        self.assertEqual(self.published_course.category, new_category)

    def test_admin_user_list_shows_deactivate_confirm_prompt(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:users"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "确定要注销这个用户吗？注销后该用户将无法登录系统。")

    def test_admin_cannot_deactivate_admin_account(self):
        second_admin = User.objects.create_user(
            email="admin2@example.com",
            username="管理员二",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("admin_panel:user-deactivate", args=[second_admin.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        second_admin.refresh_from_db()
        self.assertTrue(second_admin.is_active)

    def test_admin_user_list_hides_deactivate_action_for_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:users"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "管理员不可注销")

    def test_admin_user_list_shows_avatar_or_initial_and_comment_link(self):
        self.teacher.avatar = SimpleUploadedFile("teacher-avatar.jpg", b"avatar", content_type="image/jpeg")
        self.teacher.save(update_fields=["avatar", "updated_at"])
        student = User.objects.create_user(
            email="student-initial@example.com",
            username="小明",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:users"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.teacher.avatar.url)
        self.assertContains(response, "小明")

    def test_admin_can_delete_empty_category(self):
        empty_category = Category.objects.create(name="Design", is_active=True)
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("admin_panel:category-delete", args=[empty_category.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.filter(pk=empty_category.pk).exists())

    def test_admin_cannot_delete_category_with_courses(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("admin_panel:category-delete", args=[self.category.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_admin_can_toggle_category_active_state(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin_panel:category-toggle", args=[self.category.id]),
            {"is_active": "false"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)

    def test_admin_cannot_edit_existing_category(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin_panel:category-update", args=[self.category.id]),
            {"name": "New Name", "is_active": "on"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "IT")
