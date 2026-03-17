from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from courses.models import Course, Lesson


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="学生",
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(Course, verbose_name="课程", on_delete=models.CASCADE, related_name="enrollments")
    joined_at = models.DateTimeField("加入时间", auto_now_add=True)
    last_lesson = models.ForeignKey(
        Lesson,
        verbose_name="最近学习视频",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="last_enrollments",
    )
    last_position_seconds = models.PositiveIntegerField("最近播放秒数", default=0)
    last_learned_at = models.DateTimeField("最近学习时间", null=True, blank=True)

    class Meta:
        unique_together = [("student", "course")]
        ordering = ["-joined_at"]
        verbose_name = "选课记录"
        verbose_name_plural = "选课记录"

    def __str__(self):
        return f"{self.student} - {self.course}"


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, verbose_name="选课记录", on_delete=models.CASCADE, related_name="progresses")
    lesson = models.ForeignKey(Lesson, verbose_name="视频", on_delete=models.CASCADE, related_name="progresses")
    last_position_seconds = models.PositiveIntegerField("最后播放秒数", default=0)
    completed = models.BooleanField("是否完成", default=False)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        unique_together = [("enrollment", "lesson")]
        ordering = ["-updated_at"]
        verbose_name = "视频学习进度"
        verbose_name_plural = "视频学习进度"

    def __str__(self):
        return f"{self.enrollment} - {self.lesson}"


class Comment(models.Model):
    course = models.ForeignKey(Course, verbose_name="课程", on_delete=models.CASCADE, related_name="comments")
    lesson = models.ForeignKey(Lesson, verbose_name="视频", on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="评论用户", on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self",
        verbose_name="父评论",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    content = models.TextField("评论内容")
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="删除人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_comments",
    )
    delete_reason = models.CharField("删除原因", max_length=255, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "评论"
        verbose_name_plural = "评论"

    def clean(self):
        if self.parent and self.parent.parent_id:
            raise ValidationError("评论仅支持两层结构。")
        if self.parent and self.parent.lesson_id != self.lesson_id:
            raise ValidationError("回复必须属于同一个视频。")

    @property
    def is_deleted(self):
        return bool(self.deleted_at)

    def display_content(self):
        return "该评论已被删除" if self.is_deleted else self.content
