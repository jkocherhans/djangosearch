from itertools import islice
from django.db import models

class SearchResults(object):
    """
    Encapsulates some search results from a backend.
    
    Expects to be initalized with a query string or a SearchQuery object.
    """

    def __init__(self, query, models):
        self.query = query
        self.models = models
        from djangosearch.backends import backend
        self.backend = backend
        self.order_by = ["-relevance"]
        self.offset = 0
        self.limit = None
        
        self._result_cache = None
        
    def __iter__(self):
        return iter(self._get_results())
    
    def __len__(self):
        return len(self._get_results())
    
    def __getitem__(self, k):
        """Get an item or slice from the result set."""
        if not isinstance(k, (slice, int)):
            raise TypeError
        assert (not isinstance(k, slice) and (k >= 0)) \
            or (isinstance(k, slice) and (k.start is None or k.start >= 0) and (k.stop is None or k.stop >= 0)), \
            "Negative indexing is not supported."
        if isinstance(k, slice):
            # TODO: this should be relative to current offset/limit
            obj = self._clone()
            if k.start is not None:
                obj.offset = int(k.start)
            if k.stop is not None:
                obj.limit = int(k.stop) - obj.offset
            return k.step and list(obj)[::k.step] or obj
        return list(self._clone(offset=k, limit=1))[0]
    
    def __repr__(self):
        return "<SearchResults for %r>" % self.query
    
    # Methods that return SearchResults
    def all(self):
        return self
    
    def load_objects(self):
        """
        Returns a SearchResults with all objects in the results lodaded from 
        the database.
        
        This has better performance than the O(N) queries that iterating over
        the result set and doing ``result.object`` does; this does one
        ``in_bulk()`` call for each model in the result set.
        """
        # TODO: this is useless. this should be done in _get_results()
        original_results = []
        models_pks = {}

        # Remember the search position for each result so we don't have to resort later.
        for result in self:
            if not result._object:
                original_results.append(result)
                models_pks.setdefault(result.model, []).append(result.pk)

        # Load the objects for each model in turn
        loaded_objects = {}
        for model in models_pks:
            loaded_objects[model] = model._default_manager.in_bulk(models_pks[model])

        # Stick the result objects onto the SearchResult for returnage.
        for result in original_results:
            # We have to deal with integer keys being cast from strings; if this
            # fails we've got a character pk.
            try:
                result.pk = int(result.pk)
            except ValueError:
                pass
            try:
                result._object = loaded_objects[result.model][result.pk]
            except KeyError:
                # The object must have been deleted since we indexed; fail silently.
                continue

            return self
    
    # Methods that don't return SearchResults
    def count(self):
        return self.backend.SearchEngine().count(self.query, self.models)
    
    
    def _get_results(self):
        """
        Attempts to fetch a cached list of results, otherwise it runs the
        backends search() method.
        """
        if self._result_cache is None:
            self._result_cache = self.backend.SearchEngine().search(self.query, self.models, self.order_by, self.limit, self.offset)
        return self._result_cache
    
    def _clone(self, **kwargs):
        c = self.__class__(query=self.query, models=self.models)
        c.order_by = self.order_by
        c.offset = self.offset
        c.limit = self.limit
        c.__dict__.update(kwargs)
        return c
    
class SearchResult(object):
    """
    A single search result. If obj is supplied as a (app, model, pk) tuple, 
    the actual object is loaded lazily by accessing object.
    
    Note that if using tuples, iterating over SearchResults and getting the 
    object for each result will do O(N) database queries -- not such a great 
    idea. If you know you need the whole result set, use 
    SearchResults.load_all_results() instead.
    """
    def __init__(self, obj, score):
        if isinstance(obj, tuple):
            self.model = models.get_model(obj[0], obj[1])
            self.pk = obj[2]
            self._object = None
        else:
            self.model = obj.__class__
            self.pk = obj.pk
            self._object = obj
        self.score = score

    def __repr__(self):
        return "<SearchResult: %s(pk=%r)>" % (self.model.__name__, self.pk)

    def _get_object(self):
        if self._object is None:
            self._object = self.model._default_manager.get(pk=self.pk)
        return self._object
    object = property(_get_object)

    def content_type(self):
        return unicode(self.model._meta)

