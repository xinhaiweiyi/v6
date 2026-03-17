from django.urls import path

from learning import views


app_name = "learning"

urlpatterns = [
    path("dashboard/", views.student_dashboard, name="student-dashboard"),
    path("my/", views.student_center, name="student-center"),
    path("enroll/", views.enroll_course, name="enroll"),
    path("progress/", views.save_progress, name="progress"),
    path("courses/<slug:slug>/learn/", views.learn_course, name="learn-course"),
]
