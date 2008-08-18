
class SearchResults(object):
    """
    Encapsulates some search results from a backend.
    
    Expects to be initalized with a SearchQuery instance.
    """
    def __init__(self, query):
        self.query = query
        from djangosearch.backends import backend
        self.engine = backend.SearchEngine()
        
        self._raw_cache = None
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
        if self._result_cache is not None:
            return self._result_cache[k]
        if isinstance(k, slice):
            obj = self._clone()
            if k.start is not None:
                start = int(k.start)
            else:
                start = None
            if k.stop is not None:
                stop = int(k.stop)
            else:
                stop = None
            obj.query.set_limits(start, stop)
            return k.step and list(obj)[::k.step] or obj
        obj = self._clone()
        obj.query.set_limits(k, k+1)
        return list(obj)[0]
    
    def __repr__(self):
        return repr(list(self))
    
    # Methods that return SearchResults
    def all(self):
        """
        Returns a new SearchResults object that is a copy of the current 
        one.
        """
        return self._clone()
    
    # Methods that don't return SearchResults
    def count(self):
        """
        Returns the number of results.
        
        If the results are fully cached, the length of that will be returned. 
        Otherwise, the backend will retrieve the number of results in the most
        efficient way possible.
        """
        if self._raw_cache:
            return len(self._raw_cache)
        try:
            return self.engine.get_count(self.query)
        except NotImplementedError:
            return len(self._get_results())
    
    def raw(self):
        """
        Returns results as a list of dictionaries with 'model', 'pk' and 
        'relevance' keys.
        """
        if self._raw_cache is None:
            self._raw_cache = self.engine.get_results(self.query)
        return self._raw_cache
    
    # Private methods
    def _get_results(self):
        """
        Returns a list of result objects.
        """
        if self._result_cache is None:
            model_pks = {}
            for result in self.raw():
                model_pks.setdefault(result['model'], []).append(result['pk'])
            loaded_objects = {}
            for model in model_pks:
                loaded_objects[model] = model._default_manager.in_bulk(
                                            model_pks[model])
            self._result_cache = []
            for result in self.raw():
                # We have to deal with integer keys being cast from strings; 
                # if this fails we've got a character pk.
                try:
                    pk = int(result['pk'])
                except ValueError:
                    pk = result['pk']
                try:
                    self._result_cache.append(
                            loaded_objects[result['model']][pk])
                except KeyError:
                    # The object must have been deleted since we indexed; 
                    # fail silently. Unfortunately this will mean missing
                    # search results when paginating.
                    continue
        return self._result_cache
    
    def _clone(self, **kwargs):
        c = self.__class__(query=self.query.clone())
        c.engine = self.engine
        c.__dict__.update(kwargs)
        return c
