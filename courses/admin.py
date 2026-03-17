from django.contrib import admin

from courses.models import Category, Chapter, Course, Lesson


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "updated_at"]
    search_fields = ["name"]
    list_filter = ["is_active"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "teacher", "category", "status", "submitted_at", "published_at"]
    search_fields = ["title", "teacher__username", "teacher__email"]
    list_filter = ["status", "category"]
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "order"]
    list_filter = ["course"]
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["title", "chapter", "order", "duration_seconds"]
    search_fields = ["title", "chapter__course__title"]
