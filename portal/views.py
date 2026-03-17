from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from bishe.permissions import role_home_url, role_required
from courses.forms import CategoryForm
from courses.models import Category, Course
from learning.models import Comment, Enrollment


def home(request):
    category_slug = request.GET.get("category", "").strip()
    keyword = request.GET.get("keyword", "").strip()
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("teacher", "category")
    if category_slug:
        courses = courses.filter(category__slug=category_slug)
    if keyword:
        courses = courses.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))
    categories = Category.objects.filter(is_active=True).annotate(course_total=Count("courses"))
    return render(
        request,
        "public/home.html",
        {
            "courses": courses,
            "categories": categories,
            "selected_category": category_slug,
            "keyword": keyword,
        },
    )


def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related("teacher", "category").prefetch_related("chapters__lessons"),
        slug=slug,
        status=Course.Status.PUBLISHED,
    )
    enrollment = None
    if request.user.is_authenticated and request.user.role == "student":
        enrollment = Enrollment.objects.filter(student=request.user, course=course).select_related("last_lesson").first()
    return render(
        request,
        "public/course_detail.html",
        {"course": course, "enrollment": enrollment},
    )


@login_required
def role_home(request):
    return redirect(role_home_url(request.user))


@role_required("teacher")
def teacher_dashboard(request):
    courses = Course.objects.filter(teacher=request.user).select_related("category")
    stats = {
        "total_courses": courses.count(),
        "pending_courses": courses.filter(status=Course.Status.PENDING).count(),
        "published_courses": courses.filter(status=Course.Status.PUBLISHED).count(),
        "comments": Comment.objects.filter(course__teacher=request.user, deleted_at__isnull=True).count(),
    }
    comments = (
        Comment.objects.filter(course__teacher=request.user, deleted_at__isnull=True)
        .select_related("user", "course", "lesson")
        .order_by("-created_at")[:10]
    )
    return render(request, "teacher/dashboard.html", {"stats": stats, "comments": comments})


@role_required("admin")
def admin_dashboard(request):
    stats = {
        "student_total": User.objects.filter(role=User.Role.STUDENT, is_active=True).count(),
        "teacher_total": User.objects.filter(role=User.Role.TEACHER, is_active=True).count(),
        "course_total": Course.objects.count(),
        "pending_total": Course.objects.filter(status=Course.Status.PENDING).count(),
    }
    latest_courses = Course.objects.select_related("teacher", "category").order_by("-created_at")[:8]
    return render(request, "admin_panel/dashboard.html", {"stats": stats, "latest_courses": latest_courses})


@role_required("admin")
def admin_dashboard_data(request):
    role_label_map = dict(User.Role.choices)
    status_label_map = dict(Course.Status.choices)
    role_distribution = [
        {"role": role_label_map.get(item["role"], item["role"]), "total": item["total"]}
        for item in User.objects.filter(is_active=True).values("role").annotate(total=Count("id")).order_by("role")
    ]
    course_status = [
        {"status": status_label_map.get(item["status"], item["status"]), "total": item["total"]}
        for item in Course.objects.values("status").annotate(total=Count("id")).order_by("status")
    ]
    return JsonResponse(
        {
            "role_distribution": role_distribution,
            "course_status": course_status,
        }
    )


@role_required("admin")
def admin_user_list(request):
    keyword = request.GET.get("keyword", "").strip()
    role = request.GET.get("role", "").strip()
    ordering = request.GET.get("ordering", "-created_at")

    users = User.objects.all()
    if keyword:
        users = users.filter(Q(username__icontains=keyword) | Q(email__icontains=keyword))
    if role:
        users = users.filter(role=role)
    users = users.order_by(ordering)
    return render(
        request,
        "admin_panel/users.html",
        {
            "users": users,
            "keyword": keyword,
            "role": role,
            "ordering": ordering,
            "role_choices": User.Role.choices,
        },
    )


@role_required("admin")
@require_POST
def admin_user_deactivate(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.role == User.Role.ADMIN and User.objects.filter(role=User.Role.ADMIN, is_active=True).count() <= 1:
        messages.error(request, "至少需要保留一个可用管理员账号。")
    else:
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "用户已注销。")
    return redirect("admin_panel:users")


@role_required("admin")
def admin_comment_list(request):
    keyword = request.GET.get("keyword", "").strip()
    time_range = request.GET.get("time_range", "").strip()
    comments = (
        Comment.objects.filter(deleted_at__isnull=True)
        .select_related("user", "course", "lesson", "deleted_by")
        .order_by("-created_at")
    )
    now = timezone.now()
    if time_range == "today":
        comments = comments.filter(created_at__gte=now.replace(hour=0, minute=0, second=0, microsecond=0))
    elif time_range == "7d":
        comments = comments.filter(created_at__gte=now - timedelta(days=7))
    elif time_range == "30d":
        comments = comments.filter(created_at__gte=now - timedelta(days=30))
    if keyword:
        comments = comments.filter(
            Q(content__icontains=keyword)
            | Q(user__username__icontains=keyword)
            | Q(course__title__icontains=keyword)
        )
    return render(
        request,
        "admin_panel/comments.html",
        {
            "comments": comments,
            "keyword": keyword,
            "time_range": time_range,
            "time_choices": [
                ("", "全部时间"),
                ("today", "今天"),
                ("7d", "最近7天"),
                ("30d", "最近30天"),
            ],
        },
    )


@role_required("admin")
def admin_course_review_list(request):
    status = request.GET.get("status", "").strip()
    courses = Course.objects.select_related("teacher", "category").order_by("-submitted_at", "-updated_at")
    if status:
        courses = courses.filter(status=status)
    return render(
        request,
        "admin_panel/courses.html",
        {
            "courses": courses,
            "status": status,
            "status_choices": [("", "全部状态"), *Course.Status.choices],
        },
    )


@role_required("admin")
def admin_course_preview(request, course_id):
    course = get_object_or_404(
        Course.objects.select_related("teacher", "category").prefetch_related("chapters__lessons"),
        pk=course_id,
    )
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
            "admin_mode": True,
            "preview_base_url": reverse("admin_panel:course-preview", args=[course.id]),
        },
    )


@role_required("admin")
@require_POST
def admin_course_approve(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    course.status = Course.Status.PUBLISHED
    course.review_note = request.POST.get("review_note", "审核通过，课程已发布。").strip() or "审核通过，课程已发布。"
    course.offline_reason = ""
    course.reviewed_at = timezone.now()
    course.reviewed_by = request.user
    course.published_at = timezone.now()
    course.save()
    return JsonResponse({"ok": True, "message": "课程已审核通过。"})


@role_required("admin")
@require_POST
def admin_course_reject(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    note = request.POST.get("review_note", "").strip()
    if not note:
        return JsonResponse({"ok": False, "message": "请填写驳回原因。"}, status=400)
    course.status = Course.Status.REJECTED
    course.review_note = note
    course.reviewed_at = timezone.now()
    course.reviewed_by = request.user
    course.save()
    return JsonResponse({"ok": True, "message": "课程已驳回。"})


@role_required("admin")
@require_POST
def admin_course_offline(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    reason = request.POST.get("offline_reason", "").strip()
    if not reason:
        return JsonResponse({"ok": False, "message": "请填写下架原因。"}, status=400)
    course.status = Course.Status.OFFLINE
    course.offline_reason = reason
    course.reviewed_at = timezone.now()
    course.reviewed_by = request.user
    course.save()
    return JsonResponse({"ok": True, "message": "课程已下架。"})


@role_required("admin")
def admin_category_manage(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "课程分类已保存。")
        return redirect("admin_panel:categories")
    categories = Category.objects.annotate(course_total=Count("courses")).order_by("name")
    return render(request, "admin_panel/categories.html", {"form": form, "categories": categories})


@role_required("admin")
@require_POST
def admin_category_update(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    form = CategoryForm(request.POST, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, "课程分类已更新。")
    else:
        messages.error(request, "分类更新失败，请检查输入。")
    return redirect("admin_panel:categories")
@role_required("admin")
@require_POST
def admin_category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if category.courses.exists():
        messages.error(request, "该分类下还有课程，暂时不能删除。")
        return redirect("admin_panel:categories")
    try:
        category.delete()
    except ProtectedError:
        messages.error(request, "该分类下还有课程，暂时不能删除。")
    else:
        messages.success(request, "课程分类已删除。")
    return redirect("admin_panel:categories")
