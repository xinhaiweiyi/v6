from django.urls import path

from accounts import views


app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("send-code/", views.send_code_view, name="send-code"),
    path("profile/", views.profile_view, name="profile"),
]
