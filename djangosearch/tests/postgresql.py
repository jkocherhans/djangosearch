"""
>>> from djangosearch.query import convert_new
>>> from djangosearch.backends.postgresql import QueryConverter

>>> convert_new('(video or pictures) -(sports news) "train times" foo -boring title:foo', QueryConverter)
("(video | pictures) & !(sports & news) & 'train times' & foo & !boring", {'title': 'foo'})

"""
