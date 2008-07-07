from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from djangosearch.backends import base
from djangosearch.indexer import get_indexer, get_indexed_models
from djangosearch.query import RELEVANCE, QueryConverter, convert_new
from djangosearch.results import SearchResults


class SearchEngine(base.SearchEngine):
    """
    A MySQL FULLTEXT search engine.
    """
    
    def __init__(self):
        if settings.DATABASE_ENGINE != "mysql":
            raise ImproperlyConfigured('The mysql search engine requires the mysql database engine.')
        
    def update(self, indexer, iterable):
        pass

    def remove(self, obj):
        pass

    def clear(self, models):
        pass

    def _result_callback(self, result):
        return (result._meta.app_label, result._meta.object_name, result.pk, result.relevance)
    
    def search(self, query, models=None, order_by=RELEVANCE, limit=None, offset=None):
        (conv_query, fields) = convert_new(query, MysqlQueryConverter)
        #if not models:
        #    models = get_indexed_models()
        model = models[0] # TODO: multiple models
        index = get_indexer(model)
        table = connection.ops.quote_name(model._meta.db_table)
        matches = []
        params = []
        if conv_query:
            columns = ["%s.%s" % (table, connection.ops.quote_name(s)) 
                        for s in index.fields]
            matches.append("MATCH(%s) AGAINST (%%s IN BOOLEAN MODE)" \
                        % ", ".join(columns))
            params.append(conv_query)
        for (field, s) in fields.items():
            if field not in index.fields:
                continue
            column = "%s.%s" % (table, connection.ops.quote_name(field))
            # these fields should always be single words, so there is
            # no need for boolean mode
            matches.append("MATCH(%s) AGAINST(%%s)" % column)
            params.append(s)
        if not matches:
            return SearchResults(q, [], 0, lambda x: x)
        # maybe this shouldn't be checked so it can fall through as an
        # exception?
        sql_order_by = "-relevance"
        if order_by != RELEVANCE:
            if order_by[0] == '-':
                if order_by[1:] in index.fields:
                    sql_order_by = order_by
            else:
                if order_by in index.fields:
                    sql_order_by = order_by
                
        results = model.objects.extra(
                    select={'relevance': " + ".join(matches)}, 
                    where=matches,
                    params=params+params).order_by(sql_order_by)
        results_count = model.objects.extra(where=matches, 
                                            params=params)
        return SearchResults(query, results, results_count.count(), 
                    self._result_callback)

class MysqlQueryConverter(QueryConverter):
    QUOTES          = '""'
    GROUPERS        = "()"
    AND             = "+"
    OR              = " "
    NOT             = "-"
    SEPARATOR       = ' '
    FIELDSEP        = ':'
    
    def __init__(self):
        QueryConverter.__init__(self)
        self.in_not = False
        self.in_or = False
        
    def handle_term(self, term):
        if not self.in_quotes and not self.in_not and not self.in_or:
            self.converted.write(self.AND)
        self.converted.write(term)
        self.write_sep()
    
    def start_not(self):
        self.converted.write(self.NOT)
        self.in_not = True

    def end_not(self):
        self.in_not = False

    def start_or(self):
        self.sepstack.append(self.OR)
        self.in_or = True

    def end_or(self):
        self.in_or = False

    def start_group(self):
        if not self.in_not:
            self.converted.write(self.AND)
        self.converted.write(self.GROUPERS[0])
        