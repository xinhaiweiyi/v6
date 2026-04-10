from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.core.files.storage import default_storage
from django.test import override_settings
from unittest.mock import patch
import tempfile

from accounts.models import User
from courses.models import Category, Chapter, Course, Lesson
from learning.models import Enrollment, LessonProgress


class CourseReviewTests(TestCase):
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
        self.course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="Python 入门",
            description="课程简介",
            status=Course.Status.PENDING,
        )
        self.chapter = Chapter.objects.create(course=self.course, title="第一章", order=1)
        self.lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="第一节",
            order=1,
            duration_seconds=120,
            video=SimpleUploadedFile("demo.mp4", b"video-content", content_type="video/mp4"),
        )

    def test_admin_can_approve_course(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("admin_panel:course-approve", args=[self.course.id]),
            {"review_note": "审核通过"},
        )
        self.assertEqual(response.status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.Status.PUBLISHED)

    def test_teacher_submit_review_requires_lessons(self):
        empty_course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="空课程",
            description="尚未上传视频",
        )
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("courses:submit-review", args=[empty_course.id]))
        self.assertEqual(response.status_code, 400)

    def test_chapter_and_lesson_are_auto_ordered(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("courses:chapter-create", args=[self.course.id]), {"title": "第二章"})
        self.assertEqual(response.status_code, 302)
        chapter = Chapter.objects.get(course=self.course, title="第二章")
        self.assertEqual(chapter.order, 2)

        with patch("courses.models.extract_video_duration_seconds", return_value=90):
            response = self.client.post(
                reverse("courses:lesson-create", args=[chapter.id]),
                {
                    "title": "新视频",
                    "video": SimpleUploadedFile(
                        "next.mp4",
                        b"real-video-content-is-not-needed-for-this-test",
                        content_type="video/mp4",
                    ),
                },
            )
        self.assertEqual(response.status_code, 302)
        lesson = Lesson.objects.get(chapter=chapter, title="新视频")
        self.assertEqual(lesson.order, 1)
        self.assertEqual(lesson.duration_seconds, 90)

    def test_delete_items_reorders_remaining_sequence(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="第二节",
            order=2,
            duration_seconds=200,
            video=SimpleUploadedFile("second.mp4", b"video-content", content_type="video/mp4"),
        )
        second_chapter = Chapter.objects.create(course=self.course, title="第二章", order=2)
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("courses:lesson-delete", args=[self.lesson.id]))
        self.assertEqual(response.status_code, 302)
        second_lesson.refresh_from_db()
        self.assertEqual(second_lesson.order, 1)

        response = self.client.post(reverse("courses:chapter-delete", args=[self.chapter.id]))
        self.assertEqual(response.status_code, 302)
        second_chapter.refresh_from_db()
        self.assertEqual(second_chapter.order, 1)

    def test_teacher_can_open_own_unpublished_course_in_shared_learning_page(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="preview-target",
            order=2,
            duration_seconds=240,
            video=SimpleUploadedFile("preview.mp4", b"video-content", content_type="video/mp4"),
        )
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse("learning:learn-course", args=[self.course.slug]),
            {"lesson": second_lesson.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_lesson"].id, second_lesson.id)

    def test_admin_can_open_unpublished_course_in_shared_learning_page(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="admin-preview-target",
            order=2,
            duration_seconds=300,
            video=SimpleUploadedFile("admin-preview.mp4", b"video-content", content_type="video/mp4"),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("learning:learn-course", args=[self.course.slug]),
            {"lesson": second_lesson.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_lesson"].id, second_lesson.id)

    def test_teacher_preview_route_redirects_to_shared_learning_page(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("courses:teacher-course-preview", args=[self.course.id]))

        self.assertRedirects(response, reverse("learning:learn-course", args=[self.course.slug]))

    def test_admin_preview_route_redirects_to_shared_learning_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin_panel:course-preview", args=[self.course.id]))

        self.assertRedirects(response, reverse("learning:learn-course", args=[self.course.slug]))

    def test_course_edit_page_shows_existing_cover_preview(self):
        self.course.cover = SimpleUploadedFile("cover.png", b"fake-image-content", content_type="image/png")
        self.course.save(update_fields=["cover", "updated_at"])
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("courses:teacher-course-edit", args=[self.course.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.cover.url)

    def test_teacher_can_clear_existing_cover(self):
        self.course.cover = SimpleUploadedFile("cover.png", b"fake-image-content", content_type="image/png")
        self.course.save(update_fields=["cover", "updated_at"])
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("courses:teacher-course-edit", args=[self.course.id]),
            {
                "action": "course",
                "title": self.course.title,
                "category": self.category.id,
                "description": self.course.description,
                "remove_cover": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertFalse(self.course.cover)

    def test_teacher_can_offline_course_without_reason(self):
        self.course.status = Course.Status.PUBLISHED
        self.course.offline_reason = "old reason"
        self.course.save(update_fields=["status", "offline_reason", "updated_at"])
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("courses:teacher-course-offline", args=[self.course.id]))

        self.assertEqual(response.status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.Status.OFFLINE)
        self.assertEqual(self.course.offline_reason, "")

    def test_teacher_can_delete_course_from_management(self):
        course_to_delete = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="Delete me",
            description="Course to delete",
        )
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("courses:teacher-course-delete", args=[course_to_delete.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=course_to_delete.pk).exists())

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_teacher_delete_course_removes_cover_and_lesson_video_files(self):
        course_to_delete = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="Delete me with files",
            description="Course to delete with files",
            cover=SimpleUploadedFile("cover-delete.png", b"cover-bytes", content_type="image/png"),
        )
        chapter = Chapter.objects.create(course=course_to_delete, title="Delete chapter", order=1)
        lesson = Lesson.objects.create(
            chapter=chapter,
            title="Delete video lesson",
            order=1,
            duration_seconds=60,
            video=SimpleUploadedFile("delete-video.mp4", b"video-bytes", content_type="video/mp4"),
        )
        cover_name = course_to_delete.cover.name
        video_name = lesson.video.name
        self.assertTrue(default_storage.exists(cover_name))
        self.assertTrue(default_storage.exists(video_name))
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("courses:teacher-course-delete", args=[course_to_delete.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=course_to_delete.pk).exists())
        self.assertFalse(default_storage.exists(cover_name))
        self.assertFalse(default_storage.exists(video_name))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_teacher_delete_lesson_removes_video_file(self):
        chapter = Chapter.objects.create(course=self.course, title="Video cleanup chapter", order=99)
        lesson = Lesson.objects.create(
            chapter=chapter,
            title="Video cleanup lesson",
            order=1,
            duration_seconds=60,
            video=SimpleUploadedFile("cleanup-video.mp4", b"video-bytes", content_type="video/mp4"),
        )
        video_name = lesson.video.name
        self.assertTrue(default_storage.exists(video_name))
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("courses:lesson-delete", args=[lesson.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Lesson.objects.filter(pk=lesson.pk).exists())
        self.assertFalse(default_storage.exists(video_name))

    def test_teacher_can_view_student_progress_sorted(self):
        self.course.cover = SimpleUploadedFile("cover.png", b"fake-image-content", content_type="image/png")
        self.course.save(update_fields=["cover", "updated_at"])
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="Lesson 2",
            order=2,
            duration_seconds=150,
            video=SimpleUploadedFile("lesson2.mp4", b"video-content-2", content_type="video/mp4"),
        )
        student_a = User.objects.create_user(
            email="student-a@example.com",
            username="Alice",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        student_b = User.objects.create_user(
            email="student-b@example.com",
            username="Bob",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        enrollment_a = Enrollment.objects.create(student=student_a, course=self.course)
        enrollment_b = Enrollment.objects.create(student=student_b, course=self.course)
        LessonProgress.objects.create(enrollment=enrollment_a, lesson=self.lesson, completed=True, last_position_seconds=120)
        LessonProgress.objects.create(enrollment=enrollment_a, lesson=second_lesson, completed=True, last_position_seconds=150)
        LessonProgress.objects.create(enrollment=enrollment_b, lesson=self.lesson, completed=True, last_position_seconds=120)
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("courses:teacher-course-progress", args=[self.course.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.cover.url)
        self.assertEqual(response.context["ordering"], "-progress")
        self.assertEqual(response.context["ordering_choices"], [("-progress", "学习进度从高到低"), ("progress", "学习进度从低到高")])
        self.assertEqual(response.context["enrollments"][0].student, student_a)
        self.assertEqual(response.context["enrollments"][0].progress_percent, 100)
        self.assertEqual(response.context["enrollments"][1].progress_percent, 50)

    def test_teacher_can_view_student_progress_sorted_ascending(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="Lesson 2",
            order=2,
            duration_seconds=150,
            video=SimpleUploadedFile("lesson2-ascending.mp4", b"video-content-2", content_type="video/mp4"),
        )
        student_a = User.objects.create_user(
            email="student-a-ascending@example.com",
            username="Alice Asc",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        student_b = User.objects.create_user(
            email="student-b-ascending@example.com",
            username="Bob Asc",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        enrollment_a = Enrollment.objects.create(student=student_a, course=self.course)
        enrollment_b = Enrollment.objects.create(student=student_b, course=self.course)
        LessonProgress.objects.create(enrollment=enrollment_a, lesson=self.lesson, completed=True, last_position_seconds=120)
        LessonProgress.objects.create(enrollment=enrollment_a, lesson=second_lesson, completed=True, last_position_seconds=150)
        LessonProgress.objects.create(enrollment=enrollment_b, lesson=self.lesson, completed=True, last_position_seconds=120)
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse("courses:teacher-course-progress", args=[self.course.id]),
            {"ordering": "progress"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ordering"], "progress")
        self.assertEqual(response.context["enrollments"][0].student, student_b)
        self.assertEqual(response.context["enrollments"][1].student, student_a)
