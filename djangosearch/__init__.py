"""
Object search engine for Django
"""

from djangosearch.indexer import ModelIndex
from djangosearch.results import SearchResults

__all__ = ['search', 'ModelIndex']


def search(query, models=None):
    """
    Perform a search against the index.
    
    Arguments:
    
        ``query``
            The query string, in common query format.
            
            This is the only required argument.
            
        ``models``
            A list of models; if given only objects of this type will be 
            returned.
    """
    # Delay import of the backend so we have a chance to configure things
    # after importing search, but before we use it.
    from djangosearch.backends import backend
    return backend.SearchEngine().search(query, models)
