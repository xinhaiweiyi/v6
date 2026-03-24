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
        courses = courses.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword) | Q(teacher__username__icontains=keyword))
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
    if user.role == User.Role.ADMIN:
        messages.error(request, "管理员账号不允许注销。")
    else:
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "用户已注销。")
    return redirect("admin_panel:users")


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
        Course.objects.only("id", "slug"),
        pk=course_id,
    )
    redirect_url = course.get_learn_url()
    lesson_id = request.GET.get("lesson", "").strip()
    if lesson_id:
        redirect_url = f"{redirect_url}?lesson={lesson_id}"
    return redirect(redirect_url)


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
    get_object_or_404(Category, pk=category_id)
    messages.error(request, "已创建的分类不允许编辑。")
    return redirect("admin_panel:categories")


@role_required("admin")
@require_POST
def admin_category_toggle_active(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    category.is_active = request.POST.get("is_active") == "true"
    category.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"课程分类已{'启用' if category.is_active else '停用'}。")
    return redirect("admin_panel:categories")


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
            "categories": Category.objects.all().order_by("name"),
            "status": status,
            "status_choices": [("", "全部状态"), *Course.Status.choices],
        },
    )


@role_required("admin")
@require_POST
def admin_course_update_category(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    category = get_object_or_404(Category, pk=request.POST.get("category"))
    course.category = category
    course.save(update_fields=["category", "updated_at"])
    messages.success(request, "课程分类已更新。")
    next_url = request.POST.get("next", "").strip()
    return redirect(next_url or "admin_panel:courses")
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
