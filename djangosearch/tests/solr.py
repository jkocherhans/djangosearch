"""
>>> from djangosearch.query import convert
>>> from djangosearch.backends.solr import QueryConverter

>>> convert('(video or pictures) -(sports news) "train times" foo -boring title:foo', QueryConverter)
'(video pictures) AND NOT (sports AND news) AND "train times" AND foo AND NOT boring AND title:foo'
"""
