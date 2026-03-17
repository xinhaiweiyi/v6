from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from courses.video_utils import extract_video_duration_seconds


class Category(models.Model):
    name = models.CharField("分类名称", max_length=50, unique=True)
    slug = models.SlugField("分类标识", max_length=80, unique=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "课程分类"
        verbose_name_plural = "课程分类"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "待审核"
        PUBLISHED = "published", "已发布"
        REJECTED = "rejected", "审核不通过"
        OFFLINE = "offline", "已下架"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="授课老师",
        on_delete=models.CASCADE,
        related_name="courses",
        limit_choices_to={"role": "teacher"},
    )
    category = models.ForeignKey(Category, verbose_name="课程分类", on_delete=models.PROTECT, related_name="courses")
    title = models.CharField("课程名称", max_length=120)
    slug = models.SlugField("链接标识", max_length=150, unique=True, blank=True)
    cover = models.FileField("课程封面", upload_to="course_covers/", blank=True)
    description = models.TextField("课程简介")
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    review_note = models.TextField("审核意见", blank=True)
    offline_reason = models.TextField("下架原因", blank=True)
    submitted_at = models.DateTimeField("提交审核时间", null=True, blank=True)
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_courses",
    )
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "课程"
        verbose_name_plural = "课程"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:130] or "course"
            slug = base_slug
            index = 1
            while Course.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                index += 1
                slug = f"{base_slug}-{index}"[:150]
            self.slug = slug
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        if self.status != self.Status.PUBLISHED:
            self.published_at = self.published_at if self.published_at else None
        super().save(*args, **kwargs)

    @property
    def total_lessons(self):
        return Lesson.objects.filter(chapter__course=self).count()

    def get_learn_url(self):
        return reverse("learning:learn-course", kwargs={"slug": self.slug})


class Chapter(models.Model):
    course = models.ForeignKey(Course, verbose_name="所属课程", on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField("章节名称", max_length=120)
    order = models.PositiveIntegerField("排序", default=1)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("course", "order")]
        verbose_name = "章节"
        verbose_name_plural = "章节"

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    chapter = models.ForeignKey(Chapter, verbose_name="所属章节", on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField("视频标题", max_length=120)
    video = models.FileField("视频文件", upload_to="course_videos/%Y/%m/")
    order = models.PositiveIntegerField("排序", default=1)
    duration_seconds = models.PositiveIntegerField("视频时长(秒)", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["chapter__order", "order", "id"]
        unique_together = [("chapter", "order")]
        verbose_name = "课时视频"
        verbose_name_plural = "课时视频"

    def __str__(self):
        return self.title

    @property
    def course(self):
        return self.chapter.course

    def save(self, *args, **kwargs):
        if not self.duration_seconds and self.video:
            file_obj = getattr(self.video, "file", self.video)
            self.duration_seconds = extract_video_duration_seconds(file_obj)
        super().save(*args, **kwargs)
