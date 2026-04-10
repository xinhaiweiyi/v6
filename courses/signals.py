from django.db.models.signals import post_delete
from django.dispatch import receiver

from courses.models import Course, Lesson


def _delete_field_file(file_field):
    if not file_field:
        return
    storage = file_field.storage
    name = file_field.name
    if name and storage.exists(name):
        storage.delete(name)


@receiver(post_delete, sender=Course)
def delete_course_cover_file(sender, instance, **kwargs):
    _delete_field_file(instance.cover)


@receiver(post_delete, sender=Lesson)
def delete_lesson_video_file(sender, instance, **kwargs):
    _delete_field_file(instance.video)
