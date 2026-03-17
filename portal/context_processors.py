from courses.models import Category


def site_context(request):
    return {
        "nav_categories": Category.objects.filter(is_active=True)[:8],
    }
