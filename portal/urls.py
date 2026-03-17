from django.urls import path

from portal import views


app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("portal/", views.role_home, name="role-home"),
    path("courses/<slug:slug>/", views.course_detail, name="course-detail"),
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher-dashboard"),
]
