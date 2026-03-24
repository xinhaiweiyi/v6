from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bishe.permissions import role_home_url, role_required
from courses.models import Course, Lesson
from learning.forms import CommentForm
from learning.models import Comment, Enrollment, LessonProgress


def _attach_progress_stats(enrollments):
    for enrollment in enrollments:
        total_lessons = getattr(enrollment, "total_lessons", 0) or 0
        completed_lessons = getattr(enrollment, "completed_lessons", 0) or 0
        enrollment.progress_percent = 0 if total_lessons == 0 else int(round(completed_lessons * 100 / total_lessons))
        enrollment.total_lessons_count = total_lessons
        enrollment.completed_lessons_count = completed_lessons
    return enrollments


@role_required("student")
def student_dashboard(request):
    enrollments = list(
        Enrollment.objects.filter(student=request.user)
        .select_related("course", "course__category", "last_lesson")
        .annotate(
            total_lessons=Count("course__chapters__lessons", distinct=True),
            completed_lessons=Count("progresses", filter=Q(progresses__completed=True), distinct=True),
        )
        .order_by("-last_learned_at", "-joined_at")
    )
    _attach_progress_stats(enrollments)
    return render(
        request,
        "student/dashboard.html",
        {
            "enrollments": enrollments,
        },
    )


@role_required("student")
def student_center(request):
    comments = (
        Comment.objects.filter(user=request.user)
        .select_related("course", "lesson", "parent")
        .order_by("-created_at")
    )
    return render(
        request,
        "student/center.html",
        {"comments": comments},
    )


@role_required("student")
@require_POST
def enroll_course(request):
    course = get_object_or_404(Course, pk=request.POST.get("course_id"), status=Course.Status.PUBLISHED)
    enrollment, created = Enrollment.objects.get_or_create(student=request.user, course=course)
    message = "加入课程成功，开始学习吧。" if created else "您已加入该课程，可继续学习。"
    return JsonResponse({"ok": True, "message": message, "learn_url": course.get_learn_url()})


@role_required("student", "teacher", "admin")
def learn_course(request, slug):
    course = get_object_or_404(
        Course.objects.select_related("teacher", "category").prefetch_related(
            Prefetch("chapters__lessons", queryset=Lesson.objects.order_by("order", "id"))
        ),
        slug=slug,
    )
    enrollment = None
    if request.user.role == "student":
        if course.status != Course.Status.PUBLISHED:
            raise Http404("课程不存在。")
        enrollment = get_object_or_404(
            Enrollment.objects.select_related("last_lesson"),
            student=request.user,
            course=course,
        )
    elif request.user.role == "teacher" and course.status != Course.Status.PUBLISHED and course.teacher_id != request.user.id:
        raise Http404("课程不存在。")
    lessons = [lesson for chapter in course.chapters.all() for lesson in chapter.lessons.all()]
    lesson_id = request.GET.get("lesson")
    active_lesson = next((lesson for lesson in lessons if str(lesson.id) == lesson_id), None)
    if active_lesson is None:
        active_lesson = enrollment.last_lesson if enrollment and enrollment.last_lesson else (lessons[0] if lessons else None)

    lesson_progress = None
    start_seconds = 0
    can_track_progress = request.user.role == "student" and enrollment is not None
    if active_lesson and can_track_progress:
        lesson_progress = LessonProgress.objects.filter(enrollment=enrollment, lesson=active_lesson).first()
        start_seconds = lesson_progress.last_position_seconds if lesson_progress else enrollment.last_position_seconds

    can_comment = request.user.role == "admin" or (
        request.user.role == "teacher" and course.teacher_id == request.user.id
    ) or can_track_progress
    can_moderate_comments = request.user.role == "admin" or (
        request.user.role == "teacher" and course.teacher_id == request.user.id
    )

    back_url = role_home_url(request.user)
    back_label = "返回我的课程" if request.user.role == "student" else "返回我的主页"
    if request.user.role == "teacher" and course.teacher_id == request.user.id:
        back_url = reverse("courses:teacher-courses")
        back_label = "返回课程管理"
    elif request.user.role == "admin":
        back_url = reverse("admin_panel:courses")
        back_label = "返回课程审核"

    root_comments = (
        Comment.objects.filter(course=course, lesson=active_lesson, parent=None, deleted_at__isnull=True)
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "replies",
                queryset=Comment.objects.filter(deleted_at__isnull=True).select_related("user"),
            )
        )
        if active_lesson
        else Comment.objects.none()
    )
    return render(
        request,
        "student/learn.html",
        {
            "course": course,
            "enrollment": enrollment,
            "lessons": lessons,
            "active_lesson": active_lesson,
            "start_seconds": start_seconds,
            "comments": root_comments,
            "comment_form": CommentForm(),
            "can_track_progress": can_track_progress,
            "can_comment": can_comment,
            "can_moderate_comments": can_moderate_comments,
            "back_url": back_url,
            "back_label": back_label,
        },
    )


@role_required("student")
@require_POST
def save_progress(request):
    enrollment = get_object_or_404(
        Enrollment,
        pk=request.POST.get("enrollment_id"),
        student=request.user,
    )
    lesson = get_object_or_404(Lesson, pk=request.POST.get("lesson_id"), chapter__course=enrollment.course)
    try:
        seconds = max(int(float(request.POST.get("seconds", 0))), 0)
    except (TypeError, ValueError):
        seconds = 0
    completed = request.POST.get("completed") == "true"

    progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    progress.last_position_seconds = seconds
    progress.completed = completed
    progress.save()

    enrollment.last_lesson = lesson
    enrollment.last_position_seconds = seconds
    enrollment.last_learned_at = timezone.now()
    enrollment.save(update_fields=["last_lesson", "last_position_seconds", "last_learned_at"])
    return JsonResponse({"ok": True})


@require_POST
def create_comment(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "请先登录。"}, status=403)

    lesson = get_object_or_404(Lesson.objects.select_related("chapter__course"), pk=request.POST.get("lesson_id"))
    course = lesson.chapter.course
    parent_id = request.POST.get("parent_id")

    if request.user.role == "student":
        if not Enrollment.objects.filter(student=request.user, course=course).exists():
            return JsonResponse({"ok": False, "message": "加入课程后才能发表评论。"}, status=403)
    elif request.user.role == "teacher":
        if course.teacher_id != request.user.id:
            return JsonResponse({"ok": False, "message": "您只能回复自己课程下的评论。"}, status=403)
    elif request.user.role != "admin":
        return JsonResponse({"ok": False, "message": "无权限发表评论。"}, status=403)

    form = CommentForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "message": next(iter(form.errors.values()))[0]}, status=400)

    comment = form.save(commit=False)
    comment.user = request.user
    comment.course = course
    comment.lesson = lesson
    if parent_id:
        comment.parent = get_object_or_404(Comment, pk=parent_id, lesson=lesson)
    comment.full_clean()
    comment.save()
    return JsonResponse({"ok": True, "message": "评论已发布。"})


@require_POST
def delete_comment(request, comment_id):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "请先登录。"}, status=403)

    comment = get_object_or_404(Comment.objects.select_related("course__teacher"), pk=comment_id)
    can_delete = request.user.role == "admin" or (
        request.user.role == "teacher" and comment.course.teacher_id == request.user.id
    )
    if not can_delete:
        return JsonResponse({"ok": False, "message": "您没有删除该评论的权限。"}, status=403)

    comment.deleted_at = timezone.now()
    comment.deleted_by = request.user
    comment.delete_reason = request.POST.get("reason", "内容违规")
    comment.save(update_fields=["deleted_at", "deleted_by", "delete_reason", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "message": "评论已删除。",
            "deleted_by": request.user.display_name,
            "deleted_at": comment.deleted_at.strftime("%Y-%m-%d %H:%M"),
        }
    )
