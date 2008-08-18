import itertools
import pysolr

from django.conf import settings
from django.db import models
from django.utils.encoding import force_unicode
from djangosearch.backends import BaseSearchEngine, search
from djangosearch.query import BaseQueryConverter, convert
from djangosearch.results import SearchResults

MAX_INT = 2**31 - 1

# TODO: Support for using Solr dynnamicField declarations, the magic fieldname
# postfixes like _i for integers. Requires some sort of global field registry
# though. Is it even worth it?

class SearchEngine(BaseSearchEngine):
    def __init__(self):
        args = [settings.SOLR_URL]
        self.conn = pysolr.Solr(*args)

    def _models_query(self, models):
        def qt(model):
            return 'django_ct_s:"%s.%s"' % (model._meta.app_label, model._meta.module_name)
        return ' OR '.join([qt(model) for model in models])

    def update(self, indexer, iterable, commit=True):
        docs = []
        try:
            for obj in itertools.ifilter(indexer.should_index, iterable):
                doc = {}
                doc['id'] = self.get_identifier(obj)
                doc['django_ct_s'] = "%s.%s" % (obj._meta.app_label, obj._meta.module_name)
                doc['django_id_s'] = force_unicode(obj.pk)
                doc['text'] = indexer.flatten(obj)
                for name, value in indexer.get_additional_values(obj).items():
                    doc[name] = value
                docs.append(doc)
        except UnicodeDecodeError:
            print "Chunk failed."
            pass
        self.conn.add(docs, commit=commit)

    def remove(self, obj, commit=True):
        solr_id = self.get_identifier(obj)
        self.conn.delete(id=solr_id, commit=commit)

    def clear(self, models, commit=True):
        # *:* matches all docs in Solr
        self.conn.delete(q='*:*', commit=commit)
    
    def get_results(self, query):
        if len(str(query)) == 0:
            return []
        solr_results = self._get_results_obj(query)
        results = []
        for result in solr_results:
            app_label, model_name = result['django_ct_s'].split('.')
            results.append({
                "model": models.get_model(app_label, model_name),
                "pk": result['django_id_s'],
                "relevance": None}) # FIXME: result['score'] doesn't work for some reason 
        return results
    
    def get_count(self, query):
        if len(str(query)) == 0:
            return 0
        # if the SearchResults object covers the whole result set, just fetch
        # the number of hits and no results
        if query.high_mark is None and not query.low_mark:
            return self._get_results_obj(query.clone(high_mark=0)).hits
        # otherwise, trigger get_results()
        raise NotImplementedError
    
    def _get_results_obj(self, query):
        query.query
        conv_query = convert(str(query), QueryConverter)
        if query.models is not None:
            models_clause = self._models_query(query.models)
            final_q = '(%s) AND (%s)' % (conv_query, models_clause)
        else:
            final_q = conv_query
        kwargs = {}
        sort = []
        for s in query.order_by:
            if s[0] == '-':
                sort.append('%s desc' % s[1:].replace("relevance", "score"))
            else:
                sort.append('%s asc' % s.replace("relevance", "score"))
        if sort:
            kwargs['sort'] = ", ".join(sort)
        if query.high_mark is not None:
            kwargs['rows'] = query.high_mark - query.low_mark
        else:
            kwargs['rows'] = MAX_INT
        if query.low_mark:
            kwargs['start'] = query.low_mark
        return self.conn.search(final_q, **kwargs)


class QueryConverter(BaseQueryConverter):
    # http://wiki.apache.org/solr/SolrQuerySyntax
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " "
    NOT             = "NOT "
    SEPARATOR       = ' AND '
    FIELDSEP        = ':'
