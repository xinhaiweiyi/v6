from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from portal import views as portal_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", portal_views.home, name="home"),
    path("portal/", portal_views.role_home, name="role-home"),
    path("teacher/dashboard/", portal_views.teacher_dashboard, name="teacher-dashboard"),
    path("", include(("portal.urls", "portal"), namespace="portal")),
    path("auth/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("student/", include(("learning.urls", "learning"), namespace="learning")),
    path("teacher/", include(("courses.urls", "courses"), namespace="courses")),
    path("admin-panel/", include(("portal.admin_urls", "admin_panel"), namespace="admin_panel")),
    path("comments/", include(("learning.comment_urls", "learning"), namespace="comments")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
