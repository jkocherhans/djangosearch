from django.core.paginator import InvalidPage, ObjectPaginator as BaseObjectPaginator


class ObjectPaginator(BaseObjectPaginator):
    def __init__(self, results, num_per_page, orphans=0):
        self.results = results
        self.num_per_page = num_per_page
        self.orphans = orphans
        self._hits = self._pages = None
        self._page_range = None

    def get_page(self, page_number):
        page_number = self.validate_page_number(page_number)
        # Results should already be limited to a single page by the time they
        # are passed in.
        return list(self.results)

    def _get_hits(self):
        if self._hits is None:
            self._hits = self.results.hits
        return self._hits

    hits = property(_get_hits)
