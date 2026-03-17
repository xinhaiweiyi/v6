from django.contrib import admin

from learning.models import Comment, Enrollment, LessonProgress


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "course", "last_lesson", "last_position_seconds", "last_learned_at"]
    search_fields = ["student__email", "student__username", "course__title"]


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "lesson", "last_position_seconds", "completed", "updated_at"]
    list_filter = ["completed"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "course", "lesson", "parent", "deleted_at", "created_at"]
    search_fields = ["content", "user__username", "course__title"]
    list_filter = ["deleted_at", "course"]
