from django.db import models
from django.conf import settings
from django.shortcuts import render_to_response
from django.template import RequestContext as Context
from django import newforms as forms
from djangosearch import search
from djangosearch.paginator import SearchPaginator
from djangosearch.indexer import get_indexed_models

RESULTS_PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 20)


def model_choices():
    return ((m._meta, unicode(m._meta.verbose_name_plural)) for m in get_indexed_models())

class ModelSearchForm(forms.Form):
    query = forms.CharField(required=False)
    models = forms.MultipleChoiceField(choices=model_choices(), required=False,
        widget=forms.CheckboxSelectMultiple)

    def get_models(self):
        """Return a list of model classes specified by the models field."""
        search_models = []
        for model in self.cleaned_data['models']:
            search_models.append(models.get_model(*model.split('.')))
        if len(search_models) == 0:
            return None
        return search_models

class SearchView(object):
    def __init__(self, template=None, load_all=True):
        self.load_all = load_all
        self.template = template or 'search/search.html'

    def __call__(self, request):
        form = self.search_form(request)
        if not form.is_valid():
            raise Exception(form.errors)
        query = form.cleaned_data['query']
        search_models = form.get_models()

        try:
            page = request.GET.get('page', 1)
            page_number = int(page)
        except ValueError:
            raise Http404

        offset = (page_number - 1) * RESULTS_PER_PAGE
        results = search(query, models=search_models, limit=RESULTS_PER_PAGE, offset=offset)

        # XXX: implement load_all

        paginator = SearchPaginator(results, RESULTS_PER_PAGE)

        context = Context(request, {
            'query': query,
            'form': form,
            'page': paginator.page(page_number),
            'paginator' : paginator

        })
        return render_to_response(self.template, context_instance=context)

    def search_form(self, request):
        return ModelSearchForm(request.GET)
