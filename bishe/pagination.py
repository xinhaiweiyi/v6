from django.core.paginator import Paginator


def paginate_queryset(request, queryset_or_list, per_page):
    paginator = Paginator(queryset_or_list, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return page_obj, query_params.urlencode()
