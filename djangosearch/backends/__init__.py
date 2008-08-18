import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import force_unicode

from djangosearch.query import SearchQuery
from djangosearch.results import SearchResults

__all__ = ['backend', 'BaseSearchEngine', 'search']

def search(query, models=None):
    """
    Returns a SearchResults object containing the results.
    """
    return SearchResults(SearchQuery(query, models))

class BaseSearchEngine(object):
    """
    Abstract search engine base class.
    """
    def get_results(self, query):
        """
        Override with a method to get results for a SearchResults object.
        """
        raise NotImplementedError

    def get_count(self, query):
        """
        Override with a method to get the number of results for a 
        SearchResults object.
        """
        raise NotImplementedError

    def update(self, indexer, iterable):
        pass

    def remove(self, obj):
        pass

    def clear(self, models):
        pass

    def get_identifier(self, obj):
           """
           Get an unique identifier for the object.

           If not overridden, uses <app_label>.<object_name>.<pk>.
           """
           return "%s.%s.%s" % (obj._meta.app_label, obj._meta.module_name, obj._get_pk_val())

    def prep_value(self, db_field, value):
        """
        Hook to give the backend a chance to prep an attribute value before
        sending it to the search engine. By default, just force it to unicode.
        """
        return force_unicode(value)

# Find and load the search backend.  This code shold look pretty familier if
# you've examined django.db.backends recently...

if not hasattr(settings, "SEARCH_ENGINE"):
    if settings.DATABASE_ENGINE in ("mysql", "postgresql"):
        settings.SEARCH_ENGINE = settings.DATABASE_ENGINE
    else:
        raise ImproperlyConfigured("You must define the SEARCH_ENGINE setting "
                                   "before using the search framework.")

try:
    # Most of the time, the search backend will be one of the  
    # backends that ships with django-search, so look there first.
    backend = __import__('djangosearch.backends.%s' % settings.SEARCH_ENGINE, {}, {}, [''])
# FIXME? This gets risen when there is an ImportError risen by the backend
except ImportError, e:
    # If the import failed, we might be looking for a search backend 
    # distributed external to django-search. So we'll try that next.
    try:
        backend = __import__(settings.SEARCH_ENGINE, {}, {}, [''])
    except ImportError, e_user:
        # The database backend wasn't found. Display a helpful error message
        # listing all possible (built-in) database backends.
        backend_dir = os.path.join(__path__[0], 'backends')
        available_backends = [
            os.path.splitext(f)[0] for f in os.listdir(__path__[0])
            if not f.startswith('_') 
            and not f.startswith('.') 
            and not f.endswith('.pyc')
        ]
        available_backends.sort()
        if settings.SEARCH_ENGINE not in available_backends:
            raise ImproperlyConfigured, "%r isn't an available search backend. Available options are: %s" % \
                (settings.SEARCH_ENGINE, ", ".join(map(repr, available_backends)))
        else:
            raise # If there's some other error, this must be an error in Django itself.
