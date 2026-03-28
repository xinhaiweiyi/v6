from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from courses.models import Category, Chapter, Course, Lesson
from learning.models import Comment, Enrollment, LessonProgress


USER_PASSWORD = "Demo123456!"


def svg_cover(title, color_start, color_end):
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="{color_start}" />
          <stop offset="100%" stop-color="{color_end}" />
        </linearGradient>
      </defs>
      <rect width="1280" height="720" rx="32" fill="url(#g)" />
      <text x="96" y="280" font-size="44" font-family="Noto Sans SC, Arial, sans-serif" fill="#FFFFFF">在线视频学习系统</text>
      <text x="96" y="380" font-size="72" font-weight="700" font-family="Noto Sans SC, Arial, sans-serif" fill="#FFFFFF">{title}</text>
      <text x="96" y="460" font-size="28" font-family="Noto Sans SC, Arial, sans-serif" fill="rgba(255,255,255,0.85)">测试课程封面</text>
    </svg>
    """.strip().encode("utf-8")


def fake_video_bytes(title):
    return (
        f"这是 {title} 的测试视频占位文件。\n"
        f"创建时间：{timezone.now():%Y-%m-%d %H:%M:%S}\n"
        "用于演示课程、章节、评论和学习进度数据。\n"
    ).encode("utf-8")


class Command(BaseCommand):
    help = "创建演示用户、课程、章节、评论和学习进度数据。"

    def handle(self, *args, **options):
        with transaction.atomic():
            created = self.seed_all()
        self.stdout.write(self.style.SUCCESS("演示数据已准备完成。"))
        self.stdout.write("")
        self.stdout.write("可用测试账号：")
        for item in created["users"]:
            self.stdout.write(f"- {item['label']}：{item['email']} / {USER_PASSWORD}")
        self.stdout.write("")
        self.stdout.write(
            f"共准备：{created['category_count']} 个分类，{created['course_count']} 门课程，"
            f"{created['enrollment_count']} 条选课记录，{created['progress_count']} 条课时进度，"
            f"{created['comment_count']} 条评论。"
        )
        self.stdout.write("说明：测试视频为占位文件，主要用于功能演示，不是可播放的真实教学视频。")

    def seed_all(self):
        users = self.seed_users()
        categories = self.seed_categories()
        courses = self.seed_courses(users, categories)
        enrollments = self.seed_learning_data(users, courses)
        return {
            "users": users,
            "category_count": len(categories),
            "course_count": len(courses),
            "enrollment_count": enrollments["enrollment_count"],
            "progress_count": enrollments["progress_count"],
            "comment_count": enrollments["comment_count"],
        }

    def seed_users(self):
        definitions = [
            {"email": "admin@demo.com", "username": "系统管理员", "role": User.Role.ADMIN, "is_staff": True, "is_superuser": True, "label": "管理员"},
            {"email": "teacher1@demo.com", "username": "张老师", "role": User.Role.TEACHER, "label": "老师账号 1"},
            {"email": "teacher2@demo.com", "username": "李老师", "role": User.Role.TEACHER, "label": "老师账号 2"},
            {"email": "teacher3@demo.com", "username": "陈老师", "role": User.Role.TEACHER, "label": "老师账号 3"},
            {"email": "student1@demo.com", "username": "王小明", "role": User.Role.STUDENT, "label": "学生账号 1"},
            {"email": "student2@demo.com", "username": "赵小雨", "role": User.Role.STUDENT, "label": "学生账号 2"},
            {"email": "student3@demo.com", "username": "刘晨曦", "role": User.Role.STUDENT, "label": "学生账号 3"},
            {"email": "student4@demo.com", "username": "周可欣", "role": User.Role.STUDENT, "label": "学生账号 4"},
        ]
        created_users = []
        base_time = timezone.now() - timedelta(days=18)
        for index, item in enumerate(definitions):
            defaults = {
                "username": item["username"],
                "role": item["role"],
                "is_staff": item.get("is_staff", False),
                "is_superuser": item.get("is_superuser", False),
            }
            user, created = User.objects.get_or_create(email=item["email"], defaults=defaults)
            changed = False
            joined_at = base_time + timedelta(days=index * 2, hours=index)
            for field, value in defaults.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if user.date_joined != joined_at:
                user.date_joined = joined_at
                changed = True
            if created or not user.check_password(USER_PASSWORD):
                user.set_password(USER_PASSWORD)
                changed = True
            if changed:
                user.save()
            created_at = joined_at + timedelta(minutes=12)
            updated_fields = []
            if user.created_at != created_at:
                user.created_at = created_at
                updated_fields.append("created_at")
            if user.updated_at < created_at:
                user.updated_at = created_at
                updated_fields.append("updated_at")
            if updated_fields:
                user.save(update_fields=updated_fields)
            created_users.append(item)
        return created_users

    def seed_categories(self):
        category_names = ["IT", "外语", "设计", "办公效率", "职业成长"]
        categories = {}
        for name in category_names:
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"is_active": True},
            )
            categories[name] = category
        return categories

    def seed_courses(self, users, categories):
        teacher_map = {
            "张老师": User.objects.get(email="teacher1@demo.com"),
            "李老师": User.objects.get(email="teacher2@demo.com"),
            "陈老师": User.objects.get(email="teacher3@demo.com"),
        }
        course_specs = [
            {
                "title": "Python 零基础入门",
                "teacher": teacher_map["张老师"],
                "category": categories["IT"],
                "description": "从环境安装、变量语法到函数和项目练习，适合完全零基础同学快速上手 Python。",
                "status": Course.Status.PUBLISHED,
                "review_note": "审核通过，适合新手学习。",
                "color": ("#0369A1", "#0EA5E9"),
                "chapters": [
                    {"title": "开发环境与基础语法", "lessons": ["安装解释器", "第一个 Python 程序"]},
                    {"title": "条件、循环与函数", "lessons": ["条件分支", "循环控制", "函数封装"]},
                ],
            },
            {
                "title": "前端页面设计实战",
                "teacher": teacher_map["李老师"],
                "category": categories["设计"],
                "description": "围绕现代简洁风的页面设计方法，讲解版式、配色、卡片布局和响应式细节。",
                "status": Course.Status.PUBLISHED,
                "review_note": "审核通过，课程结构清晰。",
                "color": ("#0F766E", "#22C55E"),
                "chapters": [
                    {"title": "现代风格 UI 基础", "lessons": ["版式层级", "配色策略"]},
                    {"title": "响应式与组件设计", "lessons": ["卡片组件", "移动端适配"]},
                ],
            },
            {
                "title": "英语口语高频表达",
                "teacher": teacher_map["陈老师"],
                "category": categories["外语"],
                "description": "聚焦日常沟通、校园场景和求职面试中的高频英语表达，提升开口自信。",
                "status": Course.Status.PUBLISHED,
                "review_note": "审核通过，适合作为外语类示范课。",
                "color": ("#7C3AED", "#A855F7"),
                "chapters": [
                    {"title": "日常场景表达", "lessons": ["自我介绍", "日常问候"]},
                    {"title": "求职与面试", "lessons": ["面试开场", "项目介绍"]},
                ],
            },
            {
                "title": "Excel 办公效率提升",
                "teacher": teacher_map["张老师"],
                "category": categories["办公效率"],
                "description": "学习常用函数、透视表、图表和数据清洗，快速提升办公效率。",
                "status": Course.Status.PENDING,
                "review_note": "课程已提交，等待管理员审核。",
                "color": ("#166534", "#22C55E"),
                "chapters": [
                    {"title": "表格整理技巧", "lessons": ["基础清洗", "常用函数"]},
                ],
            },
            {
                "title": "简历优化与求职准备",
                "teacher": teacher_map["李老师"],
                "category": categories["职业成长"],
                "description": "从简历结构、项目表达、面试准备三个方面，系统梳理求职准备流程。",
                "status": Course.Status.REJECTED,
                "review_note": "请补充更多案例视频后再次提交审核。",
                "color": ("#9A3412", "#F97316"),
                "chapters": [
                    {"title": "简历优化", "lessons": ["项目描述优化"]},
                ],
            },
            {
                "title": "Django 项目开发进阶",
                "teacher": teacher_map["陈老师"],
                "category": categories["IT"],
                "description": "围绕用户系统、权限控制、课程模型和后台管理，讲解完整的 Django 项目开发思路。",
                "status": Course.Status.OFFLINE,
                "review_note": "课程已由管理员下架。",
                "offline_reason": "示例课程用于演示下架流程。",
                "color": ("#1E293B", "#475569"),
                "chapters": [
                    {"title": "权限与认证", "lessons": ["自定义用户模型", "登录权限控制"]},
                ],
            },
        ]

        created_courses = []
        for spec in course_specs:
            course, _ = Course.objects.get_or_create(
                title=spec["title"],
                teacher=spec["teacher"],
                defaults={
                    "category": spec["category"],
                    "description": spec["description"],
                    "status": spec["status"],
                    "review_note": spec.get("review_note", ""),
                    "offline_reason": spec.get("offline_reason", ""),
                },
            )
            course.category = spec["category"]
            course.description = spec["description"]
            course.status = spec["status"]
            course.review_note = spec.get("review_note", "")
            course.offline_reason = spec.get("offline_reason", "")
            if course.status == Course.Status.PUBLISHED and not course.published_at:
                course.published_at = timezone.now()
            if course.status in {Course.Status.PENDING, Course.Status.REJECTED} and not course.submitted_at:
                course.submitted_at = timezone.now()
            if course.status in {Course.Status.PUBLISHED, Course.Status.REJECTED, Course.Status.OFFLINE} and not course.reviewed_at:
                course.reviewed_at = timezone.now()
            if not course.cover:
                course.cover.save(
                    f"{course.slug or 'course'}-cover.svg",
                    ContentFile(svg_cover(spec["title"], spec["color"][0], spec["color"][1])),
                    save=False,
                )
            course.save()
            created_courses.append(course)

            for chapter_index, chapter_spec in enumerate(spec["chapters"], start=1):
                chapter, _ = Chapter.objects.get_or_create(
                    course=course,
                    order=chapter_index,
                    defaults={"title": chapter_spec["title"]},
                )
                if chapter.title != chapter_spec["title"]:
                    chapter.title = chapter_spec["title"]
                    chapter.save(update_fields=["title", "updated_at"])
                for lesson_index, lesson_title in enumerate(chapter_spec["lessons"], start=1):
                    lesson, lesson_created = Lesson.objects.get_or_create(
                        chapter=chapter,
                        order=lesson_index,
                        defaults={
                            "title": lesson_title,
                            "duration_seconds": 180 + lesson_index * 60,
                        },
                    )
                    changed = False
                    if lesson.title != lesson_title:
                        lesson.title = lesson_title
                        changed = True
                    if not lesson.duration_seconds:
                        lesson.duration_seconds = 180 + lesson_index * 60
                        changed = True
                    if lesson_created or not lesson.video:
                        lesson.video.save(
                            f"{course.slug or 'course'}-{chapter_index}-{lesson_index}.mp4",
                            ContentFile(fake_video_bytes(lesson_title)),
                            save=False,
                        )
                        changed = True
                    if changed:
                        lesson.save()
        return created_courses

    def seed_learning_data(self, users, courses):
        students = list(User.objects.filter(role=User.Role.STUDENT).order_by("email"))
        published_courses = [course for course in courses if course.status == Course.Status.PUBLISHED]
        enrollment_count = 0
        progress_count = 0
        comment_count = 0

        for student_index, student in enumerate(students):
            for course_index, course in enumerate(published_courses[:2]):
                enrollment, created = Enrollment.objects.get_or_create(
                    student=student,
                    course=course,
                )
                enrollment_count += 1 if created else 0
                course_lessons = list(
                    Lesson.objects.filter(chapter__course=course).order_by("chapter__order", "order", "id")
                )
                if not course_lessons:
                    continue

                # 为每个选课生成“已完成 + 进行中”的多课时进度，模拟真实学习轨迹。
                completed_target = min(len(course_lessons), 1 + (student_index % 3))
                in_progress_index = completed_target if completed_target < len(course_lessons) else None

                target_progress = {}
                for idx, lesson in enumerate(course_lessons):
                    if idx < completed_target:
                        target_progress[lesson.id] = (max(lesson.duration_seconds, 60), True)
                    elif in_progress_index is not None and idx == in_progress_index:
                        progress_seconds = max(30, int((lesson.duration_seconds or 180) * 0.45))
                        target_progress[lesson.id] = (progress_seconds, False)

                for lesson in course_lessons:
                    if lesson.id not in target_progress:
                        LessonProgress.objects.filter(enrollment=enrollment, lesson=lesson).delete()
                        continue

                    position_seconds, completed = target_progress[lesson.id]
                    progress, progress_created = LessonProgress.objects.get_or_create(
                        enrollment=enrollment,
                        lesson=lesson,
                        defaults={
                            "last_position_seconds": position_seconds,
                            "completed": completed,
                        },
                    )
                    progress_count += 1 if progress_created else 0
                    if (
                        progress.last_position_seconds != position_seconds
                        or progress.completed != completed
                    ):
                        progress.last_position_seconds = position_seconds
                        progress.completed = completed
                        progress.save(update_fields=["last_position_seconds", "completed", "updated_at"])

                if in_progress_index is not None:
                    last_lesson = course_lessons[in_progress_index]
                else:
                    last_lesson = course_lessons[completed_target - 1]
                last_position_seconds = target_progress[last_lesson.id][0]
                enrollment.last_lesson = last_lesson
                enrollment.last_position_seconds = last_position_seconds
                enrollment.last_learned_at = timezone.now() - timedelta(
                    days=student_index,
                    hours=course_index * 2,
                )
                enrollment.save(
                    update_fields=["last_lesson", "last_position_seconds", "last_learned_at"]
                )

        comment_samples = [
            ("student1@demo.com", "Python 零基础入门", "老师讲得很清楚，适合入门。"),
            ("student2@demo.com", "Python 零基础入门", "希望后面能多讲几个练习案例。"),
            ("student3@demo.com", "前端页面设计实战", "配色和卡片布局这部分特别实用。"),
            ("student4@demo.com", "英语口语高频表达", "跟读练习很适合日常坚持。"),
        ]

        for email, course_title, content in comment_samples:
            student = User.objects.get(email=email)
            course = Course.objects.get(title=course_title)
            lesson = Lesson.objects.filter(chapter__course=course).order_by("chapter__order", "order").first()
            comment, created = Comment.objects.get_or_create(
                course=course,
                lesson=lesson,
                user=student,
                parent=None,
                defaults={"content": content},
            )
            comment_count += 1 if created else 0
            if created:
                teacher_reply = f"{course.teacher.username}：已收到你的反馈，后续课程会继续补充案例。"
                reply, reply_created = Comment.objects.get_or_create(
                    course=course,
                    lesson=lesson,
                    user=course.teacher,
                    parent=comment,
                    defaults={"content": teacher_reply},
                )
                comment_count += 1 if reply_created else 0

        total_progress = LessonProgress.objects.filter(
            enrollment__student__role=User.Role.STUDENT,
            enrollment__course__status=Course.Status.PUBLISHED,
            enrollment__course__in=published_courses[:2],
        ).count()

        return {
            "enrollment_count": enrollment_count,
            "progress_count": max(progress_count, total_progress),
            "comment_count": comment_count,
        }
