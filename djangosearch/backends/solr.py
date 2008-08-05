from datetime import datetime, date
from pysolr import Solr
from django.conf import settings
from django.utils.encoding import force_unicode
from djangosearch.query import QueryConverter, convert as convert_query
from djangosearch.results import SearchResults, SearchResult
from djangosearch.backends.base import SearchEngine as BaseSearchEngine


# TODO: Support for using Solr dynnamicField declarations, the magic fieldname
# postfixes like _i for integers. Requires some sort of global field registry
# though. Is it even worth it?

class SearchEngine(BaseSearchEngine):
    def __init__(self):
        args = [settings.SOLR_URL]
        self.conn = Solr(*args)

    def _models_query(self, models):
        def qt(model):
            return 'django_ct_s:"%s.%s"' % (model._meta.app_label, model._meta.module_name)
        return ' OR '.join([qt(model) for model in models])

    def update(self, indexer, iterable, commit=True):
        docs = []
        try:
            for obj in iterable:
                doc = {}
                doc['id'] = self.get_identifier(obj)
                doc['django_ct_s'] = "%s.%s" % (obj._meta.app_label, obj._meta.module_name)
                doc['django_id_s'] = force_unicode(obj.pk)
                #doc['title'] = unicode(obj)
                doc['text'] = indexer.flatten(obj)
                for name, value in indexer.get_indexed_fields(obj):
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
    
    def search(self, query, models=None):
        return SearchResults(query, models)
    
    def get_results(self, query, *args, **kwargs):
        if len(query) == 0:
            return []
        solr_results = self._get_results_obj(query, *args, **kwargs)
        results = []
        for result in solr_results:
            app_label, model_name = result['django_ct_s'].split('.')
            results.append(SearchResult(
                    (app_label, model_name, result['django_id_s']),
                    None)) # FIXME: result['score'] doesn't work for some reason
        return results
    
    def get_count(self, query, *args, **kwargs):
        if len(query) == 0:
            return 0
        # if the SearchResults object covers the whole result set, just fetch
        # the number of hits and no results
        if not limit and not offset:
            kwargs['limit'] = 0
            return self._get_results_obj(query, *args, **kwargs).hits
        # otherwise, trigger get_results()
        raise NotImplementedError
    
    def _get_results_obj(self, query, models=None, limit=None, offset=None, order_by=["-relevance"]):
        original_query = query
        query = convert_query(original_query, SolrQueryConverter)
        if models is not None:
            models_clause = self._models_query(models)
            final_q = '(%s) AND (%s)' % (query, models_clause)
        else:
            final_q = query
        kwargs = {}
        sort = []
        for s in order_by:
            if s[0] == '-':
                sort.append('%s desc' % s[1:].replace("relevance", "score"))
            else:
                sort.append('%s asc' % s.replace("relevance", "score"))
        kwargs['sort'] = ", ".join(sort)   
        if limit is not None:
            kwargs['rows'] = limit
        if offset is not None:
            kwargs['start'] = offset
        return self.conn.search(final_q, **kwargs)


class SolrQueryConverter(QueryConverter):
    # http://wiki.apache.org/solr/SolrQuerySyntax
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " "
    NOT             = "NOT "
    SEPARATOR       = ' AND '
    FIELDSEP        = ':'
