import struct

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from courses.models import Category, Chapter, Course, Lesson
from learning.models import Enrollment, LessonProgress


def make_mp4_with_duration(seconds, timescale=1000):
    def make_box(box_type, payload):
        return struct.pack(">I4s", len(payload) + 8, box_type) + payload

    mvhd_payload = (
        b"\x00\x00\x00\x00"
        + struct.pack(">II", 0, 0)
        + struct.pack(">II", timescale, seconds * timescale)
        + b"\x00" * 80
    )
    ftyp_payload = b"isom" + struct.pack(">I", 0) + b"isomiso2mp41"
    return make_box(b"ftyp", ftyp_payload) + make_box(b"moov", make_box(b"mvhd", mvhd_payload))


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

        response = self.client.post(
            reverse("courses:lesson-create", args=[chapter.id]),
            {
                "title": "新视频",
                "video": SimpleUploadedFile(
                    "next.mp4",
                    make_mp4_with_duration(90),
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

    def test_teacher_preview_can_switch_active_lesson_from_query_param(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="preview-target",
            order=2,
            duration_seconds=240,
            video=SimpleUploadedFile("preview.mp4", b"video-content", content_type="video/mp4"),
        )
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse("courses:teacher-course-preview", args=[self.course.id]),
            {"lesson": second_lesson.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_lesson"].id, second_lesson.id)

    def test_admin_preview_can_switch_active_lesson_from_query_param(self):
        second_lesson = Lesson.objects.create(
            chapter=self.chapter,
            title="admin-preview-target",
            order=2,
            duration_seconds=300,
            video=SimpleUploadedFile("admin-preview.mp4", b"video-content", content_type="video/mp4"),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin_panel:course-preview", args=[self.course.id]),
            {"lesson": second_lesson.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_lesson"].id, second_lesson.id)

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

        response = self.client.get(
            reverse("courses:teacher-course-progress", args=[self.course.id]),
            {"ordering": "-progress"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.cover.url)
        self.assertEqual(response.context["enrollments"][0].student, student_a)
        self.assertEqual(response.context["enrollments"][0].progress_percent, 100)
        self.assertEqual(response.context["enrollments"][1].progress_percent, 50)
