from django.urls import path

from learning import views


urlpatterns = [
    path("create/", views.create_comment, name="create"),
    path("<int:comment_id>/delete/", views.delete_comment, name="delete"),
]
