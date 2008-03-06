"""
Tests for hyperestraier query parsing.

>>> from search.query import convert_new as convert
>>> from search.backends.estraier import HyperestraierQueryConverter

>>> original = 'kansas sports'
>>> convert(original, HyperestraierQueryConverter)
('kansas AND sports', {})



>>> original = 'author: John'
>>> convert(original, HyperestraierQueryConverter)
('', {'author': 'John'})


"""