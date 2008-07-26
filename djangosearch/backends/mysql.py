from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.query import EmptyQuerySet

from djangosearch.backends import base
from djangosearch.indexer import get_indexer, get_indexed_models
from djangosearch.query import QueryConverter, convert_new
from djangosearch.results import SearchResult
from djangosearch.utils import slicify

qn = connection.ops.quote_name

if settings.DATABASE_ENGINE != "mysql":
    raise ImproperlyConfigured('The mysql search engine requires the mysql database engine.')

class SearchEngine(base.SearchEngine):
    """
    A MySQL FULLTEXT search engine.
    """
    
    def count(self, query, models=None):
        (conv_query, fields) = convert_new(query, MysqlQueryConverter)
        if not conv_query:
            return []
        if not models:
            models = get_indexed_models()
        if len(models) == 1:
            return self._get_queryset(models[0], conv_query, fields).count()
        selects = []
        params = []
        for model in models:
            selects.append("""
            (SELECT COUNT(%(pk)s) FROM %(table)s WHERE %(match)s)
            """ % {
                "pk": qn(model._meta.pk.column),
                "table": qn(model._meta.db_table),
                "match": self._get_match(get_indexer(model).fields, model)
            })
            params.append(conv_query)
        cursor = connection.cursor()
        cursor.execute("SELECT %s" % " + ".join(selects), params)
        return cursor.fetchone()[0]
        
    def search(self, query, models=None, order_by=["-relevance"], limit=None, offset=None):
        (conv_query, fields) = convert_new(query, MysqlQueryConverter)
        if not conv_query:
            return []
        if not models:
            models = get_indexed_models()
        if len(models) == 1:
            qs = self._get_queryset(models[0], conv_query, fields, order_by)
            qs = slicify(qs, limit, offset)
            return [SearchResult(obj, obj.relevance) for obj in qs]
        selects = []
        params = []
        for model in models:
            table = qn(model._meta.db_table)
            selects.append("""
            (SELECT %%s, %%s, %(pk)s, %(match)s as relevance
            FROM %(table)s
            WHERE %(match)s)""" % {
                'pk': "%s.%s" % (table, qn(model._meta.pk.column)),
                'table': table,
                'match': self._get_match(get_indexer(model).fields, model),
            })
            params.extend([
                model._meta.app_label,
                model._meta.object_name,
                conv_query,
                conv_query,
            ])
        cursor = connection.cursor()
        sql = "%s ORDER BY relevance DESC" % " UNION ".join(selects)
        if limit:
            sql += " LIMIT %d" % limit
        if offset:
            if limit is None:
                sql += " LIMIT %d" % connection.ops.no_limit_value()
            sql += " OFFSET %d" % offset
        cursor.execute(sql, params)
        return [SearchResult((r[0], r[1], r[2]), r[3]) 
                    for r in cursor.fetchall()]
    
    def _get_queryset(self, model, query=None, fields={}, order_by=None):
        index = get_indexer(model)
        matches = []
        params = []
        if query:
            matches.append(self._get_match(index.fields, model))
            params.append(query)
        for (field, s) in fields.items():
            if field not in index.fields:
                continue
            # these fields should always be single words, so there is
            # no need for boolean mode
            matches.append(self._get_match([field], model, False))
            params.append(s)
        if not matches:
            return EmptyQuerySet(model)
        return model.objects.extra(
                    select={'relevance': " + ".join(matches)},
                    select_params=params,
                    where=matches,
                    params=params,
                    order_by=order_by)
            
    def _get_match(self, fields, model, bool_mode=True):
        columns = ["%s.%s" % (qn(model._meta.db_table), qn(s)) 
                    for s in fields]
        m = "MATCH(%s) AGAINST(%%s" % ", ".join(columns)
        if bool_mode:
            m += " IN BOOLEAN MODE"
        return m + ")"
        
    def update(self, indexer, iterable):
            pass

    def remove(self, obj):
        pass

    def clear(self, models):
        pass
    

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
        