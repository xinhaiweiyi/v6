from datetime import timedelta

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

    def test_admin_comment_list_links_to_exact_comment_area(self):
        chapter = Chapter.objects.create(course=self.published_course, title="第一章", order=1)
        lesson = Lesson.objects.create(
            chapter=chapter,
            title="第一节",
            order=1,
            duration_seconds=120,
            video="course_videos/test.mp4",
        )
        student = User.objects.create_user(
            email="student@example.com",
            username="学生",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        comment = Comment.objects.create(
            course=self.published_course,
            lesson=lesson,
            user=student,
            content="测试评论",
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:comments"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{reverse("learning:learn-course", args=[self.published_course.slug])}?lesson={lesson.id}#comment-{comment.id}',
        )

    def test_admin_comment_list_hides_deleted_comments(self):
        chapter = Chapter.objects.create(course=self.published_course, title="第二章", order=2)
        lesson = Lesson.objects.create(
            chapter=chapter,
            title="第二节",
            order=1,
            duration_seconds=90,
            video="course_videos/test-2.mp4",
        )
        student = User.objects.create_user(
            email="student2@example.com",
            username="学生二号",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        visible_comment = Comment.objects.create(
            course=self.published_course,
            lesson=lesson,
            user=student,
            content="可见评论",
        )
        hidden_comment = Comment.objects.create(
            course=self.published_course,
            lesson=lesson,
            user=student,
            content="已删除评论",
        )
        hidden_comment.deleted_by = self.admin_user
        hidden_comment.deleted_at = hidden_comment.created_at
        hidden_comment.save(update_fields=["deleted_by", "deleted_at", "updated_at"])
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:comments"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible_comment.content)
        self.assertNotContains(response, hidden_comment.content)

    def test_admin_comment_list_can_filter_by_time_range(self):
        chapter = Chapter.objects.create(course=self.published_course, title="第三章", order=3)
        lesson = Lesson.objects.create(
            chapter=chapter,
            title="第三节",
            order=1,
            duration_seconds=60,
            video="course_videos/test-3.mp4",
        )
        student = User.objects.create_user(
            email="student3@example.com",
            username="学生三号",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        recent_comment = Comment.objects.create(
            course=self.published_course,
            lesson=lesson,
            user=student,
            content="最近评论",
        )
        older_comment = Comment.objects.create(
            course=self.published_course,
            lesson=lesson,
            user=student,
            content="较早评论",
        )
        Comment.objects.filter(pk=recent_comment.pk).update(created_at=timezone.now() - timedelta(days=1))
        Comment.objects.filter(pk=older_comment.pk).update(created_at=timezone.now() - timedelta(days=10))
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:comments"), {"time_range": "7d"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, recent_comment.content)
        self.assertNotContains(response, older_comment.content)

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
