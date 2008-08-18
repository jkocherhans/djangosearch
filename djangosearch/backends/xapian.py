from datetime import datetime
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from djangosearch.query import RELEVANCE, QueryConverter
from djangosearch.results import SearchResults
from djangosearch.backends import base

import xapian

# Using Q as a UID prefix seems to be standard, undocumented practice in the
# xapian community
DOC_ID_TERM_PREFIX = 'Q'
DOC_ID_VALUE_INDEX = 0

class SearchEngine(base.SearchEngine):
    """
    A search engine for local Xapian databases.
    """
    def _read_only_db(self):
        """Retruns a read-only xapian Database object."""
        return xapian.Database(settings.SEARH_INDEX_PATH, xapian.DB_CREATE_OR_OPEN)

    def _read_write_db(self):
        """Retruns a read-write xapian Database object."""
        return xapian.WritableDatabase(settings.SEARH_INDEX_PATH, xapian.DB_CREATE_OR_OPEN)

    def update(self, indexer, iterable):
        for obj in iterable:
            doc_id = self.get_identifier(obj)
            doc = xapian.Document()
            doc.add_term(DOC_ID_TERM_PREFIX + doc_id)
            doc.add_value(DOC_ID_VALUE_INDEX, doc_id)
            # Index the object.
            indexer.flatten(object)
            # Index field values.
            for name, value in indexer.get_field_values(obj).items():
                doc.add_term(name.upper(), value)
                #doc.add_value(0, value)
            db = self._read_write_db()
            # db.replace_document will create a new doc if a doc matching
            # doc_id is not found.
            xap_doc_id = db.replace_document(doc_id, doc)
            # XXX: close the db, or make sure it runs in its own thread. Only
            # 1 writable connection can be open at a time.

    def remove(self, obj):
        """Remove an object from its node."""
        # XXX: broken for now. obj._get_pk_val() is None once post_save is
        # sent. There is a message to django-dev regarding a fix for that.
        db.delete_document(DOC_ID_TERM_PREFIX + self.get_identifier(obj))

    def clear(self, models):
        # TODO: Implement me.
        raise NotImplementedError

    def prep_value(self, db_field, value):
        """
        Hook to give the backend a chance to prep an attribute value before
        sending it to the search engine. By default, just return str(value).
        """
        # TODO: zero pad anything that should be treated as a number. xapian
        # only deals with strings for ordering, so we have to fake it.
        return str(value)

    def _result_callback(self, doc):
        """
        Extract and return (app_label, model_name, pk, score) for the given
        xapian.Document.
        """
        app_label, model_nam, pk_val = doc.get_value(DOC_ID_VALUE_INDEX).split('.')
        return (app_label, model_name, pk_val, 0)

    def search(self, query, models=None, order_by=RELEVANCE, limit=25, offset=0):
        db = self._read_only_db()
        # TODO: implement me
        return SearchResults(query, results, self._result_callback)

class XapianQueryConverter(QueryConverter):
    # http://xapian.org/docs/queryparser.html
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " OR "
    NOT             = "NOT "
    SEPARATOR       = ' AND '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'
