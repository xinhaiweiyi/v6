from django.urls import path

from portal import views


app_name = "admin_panel"

urlpatterns = [
    path("", views.admin_dashboard, name="admin-dashboard"),
    path("dashboard/data/", views.admin_dashboard_data, name="dashboard-data"),
    path("users/", views.admin_user_list, name="users"),
    path("users/<int:user_id>/deactivate/", views.admin_user_deactivate, name="user-deactivate"),
    path("courses/", views.admin_course_review_list, name="courses"),
    path("courses/<int:course_id>/category/", views.admin_course_update_category, name="course-update-category"),
    path("courses/<int:course_id>/preview/", views.admin_course_preview, name="course-preview"),
    path("courses/<int:course_id>/approve/", views.admin_course_approve, name="course-approve"),
    path("courses/<int:course_id>/reject/", views.admin_course_reject, name="course-reject"),
    path("courses/<int:course_id>/offline/", views.admin_course_offline, name="course-offline"),
    path("categories/", views.admin_category_manage, name="categories"),
    path("categories/<int:category_id>/edit/", views.admin_category_update, name="category-update"),
    path("categories/<int:category_id>/toggle/", views.admin_category_toggle_active, name="category-toggle"),
    path("categories/<int:category_id>/delete/", views.admin_category_delete, name="category-delete"),
]
