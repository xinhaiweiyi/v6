from django.urls import path

from courses import views


app_name = "courses"

urlpatterns = [
    path("", views.teacher_course_list, name="teacher-courses"),
    path("courses/create/", views.teacher_course_create, name="teacher-course-create"),
    path("courses/<int:course_id>/edit/", views.teacher_course_edit, name="teacher-course-edit"),
    path("courses/<int:course_id>/offline/", views.teacher_course_offline, name="teacher-course-offline"),
    path("courses/<int:course_id>/progress/", views.teacher_course_progress, name="teacher-course-progress"),
    path("courses/<int:course_id>/submit-review/", views.submit_review, name="submit-review"),
    path("courses/<int:course_id>/chapters/add/", views.chapter_create, name="chapter-create"),
    path("chapters/<int:chapter_id>/delete/", views.chapter_delete, name="chapter-delete"),
    path("chapters/<int:chapter_id>/lessons/add/", views.lesson_create, name="lesson-create"),
    path("lessons/<int:lesson_id>/delete/", views.lesson_delete, name="lesson-delete"),
    path("courses/<int:course_id>/preview/", views.teacher_course_preview, name="teacher-course-preview"),
]
