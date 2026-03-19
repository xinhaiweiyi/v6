from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from courses.models import Category, Chapter, Course, Lesson
from learning.models import Comment, Enrollment, LessonProgress


class LearningFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com",
            username="Student",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            username="Teacher",
            password="StrongPass123!",
            role=User.Role.TEACHER,
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            username="Admin",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.category = Category.objects.create(name="Design", is_active=True)
        self.course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="UI Design Course",
            description="Course description",
            status=Course.Status.PUBLISHED,
        )
        chapter = Chapter.objects.create(course=self.course, title="Chapter 1", order=1)
        self.lesson = Lesson.objects.create(
            chapter=chapter,
            title="Lesson 1",
            order=1,
            duration_seconds=180,
            video=SimpleUploadedFile("lesson.mp4", b"video-content", content_type="video/mp4"),
        )

    def test_student_can_enroll_and_save_progress(self):
        self.client.force_login(self.student)
        enroll_response = self.client.post(reverse("learning:enroll"), {"course_id": self.course.id})
        self.assertEqual(enroll_response.status_code, 200)
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)

        progress_response = self.client.post(
            reverse("learning:progress"),
            {"enrollment_id": enrollment.id, "lesson_id": self.lesson.id, "seconds": 42, "completed": "false"},
        )
        self.assertEqual(progress_response.status_code, 200)
        progress = LessonProgress.objects.get(enrollment=enrollment, lesson=self.lesson)
        self.assertEqual(progress.last_position_seconds, 42)

    def test_student_dashboard_only_shows_joined_courses_with_cover(self):
        self.course.cover = SimpleUploadedFile("cover.jpg", b"cover-image", content_type="image/jpeg")
        self.course.save(update_fields=["cover", "updated_at"])
        second_course = Course.objects.create(
            teacher=self.teacher,
            category=self.category,
            title="Second Course",
            description="Second course description",
            status=Course.Status.PUBLISHED,
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        Enrollment.objects.create(student=self.student, course=second_course)
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:student-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertContains(response, second_course.title)
        self.assertContains(response, self.course.cover.url)
        self.assertNotContains(response, "推荐课程")

    def test_student_dashboard_shows_progress_percentage(self):
        enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        LessonProgress.objects.create(enrollment=enrollment, lesson=self.lesson, completed=True, last_position_seconds=180)
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:student-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100%")
        self.assertContains(response, "已完成 1/1 节视频")

    def test_teacher_can_delete_comment_under_own_course(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        comment = Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="test")
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("comments:delete", args=[comment.id]), {"reason": "rule"})

        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertIsNotNone(comment.deleted_at)

    def test_teacher_can_open_published_course_without_enrollment(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

    def test_admin_can_open_published_course_without_enrollment(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lesson.title)

    def test_learning_page_uses_non_overlapping_player_layout(self):
        self.client.force_login(self.student)
        Enrollment.objects.create(student=self.student, course=self.course)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "learning-player-shell")
        self.assertContains(response, 'class="min-w-0 space-y-6"')

    def test_teacher_dashboard_links_to_exact_comment_area(self):
        comment = Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="need help")
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("portal:teacher-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{reverse("learning:learn-course", args=[self.course.slug])}?lesson={self.lesson.id}#comment-{comment.id}',
        )

    def test_teacher_can_see_delete_control_in_comment_area(self):
        comment = Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="delete me")
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-delete-comment')
        self.assertContains(response, f'data-comment-id="{comment.id}"')

    def test_deleted_comment_is_hidden_from_comment_area(self):
        comment = Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="hide me")
        comment.deleted_at = comment.created_at
        comment.deleted_by = self.teacher
        comment.delete_reason = "rule"
        comment.save(update_fields=["deleted_at", "deleted_by", "delete_reason", "updated_at"])
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hide me")

    def test_student_comment_page_only_shows_comment_section(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        comment = Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="my comment")
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:student-center"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "我的评论")
        self.assertContains(response, comment.content)
        self.assertNotContains(response, "我的课程与评论")

    def test_comment_area_shows_avatar_or_initial(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.student.avatar = SimpleUploadedFile("avatar.jpg", b"avatar-image", content_type="image/jpeg")
        self.student.save(update_fields=["avatar", "updated_at"])
        other_student = User.objects.create_user(
            email="student4@example.com",
            username="Alice",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        Comment.objects.create(course=self.course, lesson=self.lesson, user=self.student, content="avatar")
        Comment.objects.create(course=self.course, lesson=self.lesson, user=other_student, content="initial")
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:learn-course", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.avatar.url)
        self.assertContains(response, "Alice")
        self.assertContains(response, 'rounded-full bg-sky-100')
