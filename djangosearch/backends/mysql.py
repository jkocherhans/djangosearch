from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.query import EmptyQuerySet

from djangosearch.backends import base
from djangosearch.indexer import get_indexer
from djangosearch.query import QueryConverter, convert_new

qn = connection.ops.quote_name

if settings.DATABASE_ENGINE != "mysql":
    raise ImproperlyConfigured('The mysql search engine requires the mysql database engine.')

class SearchEngine(base.SearchEngine):
    """
    A MySQL FULLTEXT search engine.
    """
    def search(self, query, models=None):
        assert models and len(models) == 1, \
                "This search backend only supports searching single models."
        model = models[0]
        index = get_indexer(model)
        table = qn(model._meta.db_table)
        (conv_query, fields) = convert_new(query, MysqlQueryConverter)
        matches = []
        params = []
        if conv_query:
            columns = ["%s.%s" % (table, qn(s)) for s in index.fields]
            matches.append("MATCH(%s) AGAINST (%%s IN BOOLEAN MODE)" \
                        % ", ".join(columns))
            params.append(conv_query)
        for (field, s) in fields.items():
            if field not in index.fields:
                continue
            column = "%s.%s" % (table, qn(field))
            # these fields should always just be text, so there is
            # no need for boolean mode
            matches.append("MATCH(%s) AGAINST(%%s)" % column)
            params.append(s)
        if not matches:
            return EmptyQuerySet(model)
        return model.objects.extra(
                    # TODO: this isn't an ideal solution for relevance
                    # weighting?
                    select={'relevance': " + ".join(matches)},
                    select_params=params,
                    where=matches,
                    params=params,
                    # FIXME: relevance can't be used outside extra()
                    order_by=["-relevance"])
    

class MysqlQueryConverter(QueryConverter):
    # http://dev.mysql.com/doc/refman/5.0/en/fulltext-boolean.html
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
        