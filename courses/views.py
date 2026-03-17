from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bishe.permissions import role_required
from courses.forms import CategoryForm, ChapterForm, CourseForm, LessonForm
from courses.models import Category, Chapter, Course, Lesson


def _next_chapter_order(course):
    return (course.chapters.order_by("-order").values_list("order", flat=True).first() or 0) + 1


def _next_lesson_order(chapter):
    return (chapter.lessons.order_by("-order").values_list("order", flat=True).first() or 0) + 1


def _renumber_chapters(course):
    for index, chapter in enumerate(course.chapters.order_by("order", "id"), start=1):
        if chapter.order != index:
            chapter.order = index
            chapter.save(update_fields=["order", "updated_at"])


def _renumber_lessons(chapter):
    for index, lesson in enumerate(chapter.lessons.order_by("order", "id"), start=1):
        if lesson.order != index:
            lesson.order = index
            lesson.save(update_fields=["order", "updated_at"])


@role_required("teacher")
def teacher_course_list(request):
    status = request.GET.get("status", "")
    keyword = request.GET.get("keyword", "").strip()
    courses = Course.objects.filter(teacher=request.user).select_related("category")
    if status:
        courses = courses.filter(status=status)
    if keyword:
        courses = courses.filter(title__icontains=keyword)
    return render(
        request,
        "teacher/course_list.html",
        {
            "courses": courses,
            "status": status,
            "keyword": keyword,
            "status_choices": Course.Status.choices,
        },
    )


@role_required("teacher")
def teacher_course_create(request):
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        if form.cleaned_data.get("remove_cover") and course.cover:
            course.cover.delete(save=False)
            course.cover = None
        course.teacher = request.user
        course.save()
        messages.success(request, "课程已创建，请继续完善章节与视频内容。")
        return redirect("courses:teacher-course-edit", course_id=course.id)
    return render(request, "teacher/course_form.html", {"form": form, "course": None})


@role_required("teacher")
def teacher_course_edit(request, course_id):
    course = get_object_or_404(
        Course.objects.prefetch_related("chapters__lessons").select_related("category"),
        pk=course_id,
        teacher=request.user,
    )
    original_status = course.status
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    chapter_form = ChapterForm()

    if request.method == "POST" and request.POST.get("action") == "course" and form.is_valid():
        updated_course = form.save(commit=False)
        if form.cleaned_data.get("remove_cover") and updated_course.cover:
            updated_course.cover.delete(save=False)
            updated_course.cover = None
        if original_status == Course.Status.PUBLISHED:
            updated_course.status = Course.Status.PENDING
            updated_course.review_note = "课程内容已更新，等待重新审核。"
            updated_course.submitted_at = timezone.now()
            updated_course.reviewed_at = None
            updated_course.reviewed_by = None
        updated_course.save()
        messages.success(request, "课程信息已保存。")
        return redirect("courses:teacher-course-edit", course_id=course.id)

    return render(
        request,
        "teacher/course_form.html",
        {
            "form": form,
            "course": course,
            "chapter_form": chapter_form,
            "lesson_form": LessonForm(),
        },
    )


@role_required("teacher")
def chapter_create(request, course_id):
    course = get_object_or_404(Course, pk=course_id, teacher=request.user)
    form = ChapterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        chapter = form.save(commit=False)
        chapter.course = course
        chapter.order = _next_chapter_order(course)
        chapter.save()
        messages.success(request, "章节已添加，系统已自动排到最后。")
    else:
        messages.error(request, "章节添加失败，请检查输入。")
    return redirect("courses:teacher-course-edit", course_id=course.id)


@role_required("teacher")
@require_POST
def chapter_delete(request, chapter_id):
    chapter = get_object_or_404(
        Chapter.objects.select_related("course"),
        pk=chapter_id,
        course__teacher=request.user,
    )
    course = chapter.course
    chapter.delete()
    _renumber_chapters(course)
    messages.success(request, "章节已删除，剩余章节顺序已自动重排。")
    return redirect("courses:teacher-course-edit", course_id=course.id)


@role_required("teacher")
def lesson_create(request, chapter_id):
    chapter = get_object_or_404(
        Chapter.objects.select_related("course"),
        pk=chapter_id,
        course__teacher=request.user,
    )
    form = LessonForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        lesson = form.save(commit=False)
        lesson.chapter = chapter
        lesson.order = _next_lesson_order(chapter)
        lesson.save()
        messages.success(request, "视频已上传，系统已自动排到本章节最后。")
    else:
        messages.error(request, "视频上传失败，请检查文件和表单。")
    return redirect("courses:teacher-course-edit", course_id=chapter.course_id)


@role_required("teacher")
@require_POST
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("chapter__course"),
        pk=lesson_id,
        chapter__course__teacher=request.user,
    )
    chapter = lesson.chapter
    course_id = chapter.course_id
    lesson.delete()
    _renumber_lessons(chapter)
    messages.success(request, "视频已删除，剩余视频顺序已自动重排。")
    return redirect("courses:teacher-course-edit", course_id=course_id)


@role_required("teacher")
@require_POST
def submit_review(request, course_id):
    course = get_object_or_404(Course, pk=course_id, teacher=request.user)
    if not course.chapters.exists() or not Lesson.objects.filter(chapter__course=course).exists():
        return JsonResponse({"ok": False, "message": "请至少添加一个章节和一个视频后再提交审核。"}, status=400)
    course.status = Course.Status.PENDING
    course.submitted_at = timezone.now()
    course.review_note = "课程已提交，等待管理员审核。"
    course.reviewed_at = None
    course.reviewed_by = None
    course.save(update_fields=["status", "submitted_at", "review_note", "reviewed_at", "reviewed_by", "updated_at"])
    return JsonResponse({"ok": True, "message": "课程已提交审核。"})


@role_required("teacher")
@require_POST
def teacher_course_offline(request, course_id):
    course = get_object_or_404(Course, pk=course_id, teacher=request.user)
    course.status = Course.Status.OFFLINE
    course.offline_reason = request.POST.get("offline_reason", "老师主动下架课程").strip() or "老师主动下架课程"
    course.review_note = "课程已由老师主动下架。"
    course.save(update_fields=["status", "offline_reason", "review_note", "updated_at"])
    return JsonResponse({"ok": True, "message": "课程已下架。"})


@login_required
def teacher_course_preview(request, course_id):
    course = get_object_or_404(
        Course.objects.select_related("teacher", "category").prefetch_related("chapters__lessons"),
        pk=course_id,
    )
    if request.user.role == "teacher" and course.teacher_id != request.user.id:
        return redirect("courses:teacher-courses")
    if request.user.role not in {"teacher", "admin"}:
        return redirect("portal:home")
    lessons = [lesson for chapter in course.chapters.all() for lesson in chapter.lessons.all()]
    lesson_id = request.GET.get("lesson")
    active_lesson = next((lesson for lesson in lessons if str(lesson.id) == lesson_id), None)
    if active_lesson is None:
        active_lesson = lessons[0] if lessons else None
    return render(
        request,
        "teacher/course_preview.html",
        {
            "course": course,
            "active_lesson": active_lesson,
            "lessons": lessons,
            "preview_base_url": reverse("courses:teacher-course-preview", args=[course.id]),
        },
    )


@role_required("admin")
def admin_category_manage(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "课程分类已保存。")
        return redirect("admin_panel:categories")
    categories = Category.objects.all()
    return render(request, "admin_panel/categories.html", {"form": form, "categories": categories})
