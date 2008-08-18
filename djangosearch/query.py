"""
Provides a common query language for all backends.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import pyparsing

START, END, TERM = ("start", "end", "term")

class SearchQuery(object):
    """
    A search query.
    
    Expects to be initialised with a query string in common query format,    
    and an optional list of models to limit the search to.
    """
    def __init__(self, query, models=None):
        self.query = query
        self.models = models
    
        self.order_by = ["-relevance"]
        self.low_mark, self.high_mark = 0, None  # Used for offset/limit
    
    def __str__(self):
        return self.query
        
    def __repr__(self):
        return "<SearchQuery for %r>" % self.query
    
    def clone(self, **kwargs):
        c = self.__class__(query=self.query, models=self.models)
        c.order_by = self.order_by
        c.low_mark = self.low_mark
        c.high_mark = self.high_mark
        c.__dict__.update(kwargs)
        return c
    
    def set_limits(self, low=None, high=None):
        """
        Adjusts the limits on the results retrieved. We use low/high to set 
        these, as it makes it more Pythonic to read and write.

        Any limits passed in here are applied relative to the existing
        constraints. So low is added to the current low value and both will be
        clamped to any existing high value.
        """
        if high is not None:
            if self.high_mark:
                self.high_mark = min(self.high_mark, self.low_mark + high)
            else:
                self.high_mark = self.low_mark + high
        if low is not None:
            if self.high_mark:
                self.low_mark = min(self.high_mark, self.low_mark + low)
            else:
                self.low_mark = self.low_mark + low

    def clear_limits(self):
        """
        Clears any existing limits.
        """
        self.low_mark, self.high_mark = 0, None

class BaseQueryConverter(object):
    """
    Abstract search query converter base class. This will actually work, if by
    "work" you mean "echo the orginal query string"...
    
    For most real-world syntaxes, overriding the constants below should work
    to make a custom search grammar, but you can override methods and do
    anything, really.
    """

    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " or "
    NOT             = "-"
    SEPARATOR       = ' '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'

    def __init__(self):
        self.converted = StringIO()
        self.in_quotes = False
        self.sepstack = []

    def __str__(self):
        s = self.converted.getvalue()
        if s.endswith(self.SEPARATOR):
            s = s[:-len(self.SEPARATOR)]
        return s

    def handle_term(self, term):
        self.converted.write(term)
        self.write_sep()

    def write_sep(self):
        if self.sepstack:
            sep = self.sepstack.pop()
        elif self.in_quotes:
            sep = self.IN_QUOTES_SEP
        else:
            sep = self.SEPARATOR
        self.converted.write(sep)

    def start_quotes(self):
        self.in_quotes = True
        self.converted.write(self.QUOTES[0])

    def end_quotes(self):
        self.converted.seek(-len(self.IN_QUOTES_SEP), 1)
        self.converted.write(self.QUOTES[1])
        self.in_quotes = False
        self.write_sep()

    def start_group(self):
        self.converted.write(self.GROUPERS[0])

    def end_group(self):
        # remove an extraneous seperator from the end of the group
        self.converted.seek(-len(self.SEPARATOR), 1)
        self.converted.write(self.GROUPERS[1])
        self.write_sep()

    def start_not(self):
        self.converted.write(self.NOT)

    def start_fieldname(self):
        self.sepstack.append(self.FIELDSEP)

    def start_or(self):
        self.sepstack.append(self.OR)

def convert(query_string, converter_class):
    """
    Convert a query string in common format into a backend-specific format,
    given a a converter class to handle callbacks (see QueryConverter in
    search.base).
    """
    # Don't pass empty strings into pyparsing. It's fussy about that.
    if len(query_string) == 0:
        return query_string
    c = converter_class()
    for action, arg in parse(query_string):
        if action == TERM:
            c.handle_term(arg)
        else:
            callback = getattr(c, "%s_%s" % (action, arg), None)
            if callback:
                callback()
    return str(c)

def convert_new(query_string, converter_class):
    """
    Convert a query string in common format into a backend-specific format,
    given a a converter class to handle callbacks (see QueryConverter in
    search.base).
    """
    fields = {}
    c = converter_class()
    # track the state of a few things while we're parsing the event steam
    parsing_fieldname = False # are we parsing a fieldname?
    parsing_fieldval = False # are we parsing a field value?
    current_fieldname = None # what is the name of the field we are parsing?
    # parse the event stream
    for action, arg in parse(query_string):
        if action == TERM:
            if parsing_fieldname:
                current_fieldname = arg
            elif parsing_fieldval:
                fields[current_fieldname] = arg
            else:
                c.handle_term(arg)
        elif action == START and arg == 'fieldname':
            parsing_fieldname = True
        elif action == END and arg == 'fieldname':
            parsing_fieldname = False
        elif action == START and arg == 'field':
            parsing_fieldval = True
        elif action == END and arg == 'field':
            parsing_fieldval = False
        else:
            callback = getattr(c, "%s_%s" % (action, arg), None)
            if callback:
                callback()
    return (str(c), fields)

def parse(query_string):
    """
    Parse a common query string into an event stream.
    
    The event stream is a series of tuples: (action, arg). Each action is one
    of the module constants START, END, or TERM; the arg is the event to
    start/end or the term itself.
    
    For example, the search string "django rocks author:jacob" yields this
    event stream::
          
        [(TERM,  'django'),
         (TERM,  'rocks'),
         (START, 'field'),
         (START, 'fieldname'),
         (TERM,  'author'),
         (END,   'fieldname'),
         (TERM,  'jacob'),
         (END,   'field')]
    """
    return _event_generator(_parser(query_string))

def _event_generator(stream):
    for n in stream:
        if isinstance(n, pyparsing.ParseResults):
            yield ("start", n.getName())
            for event in _event_generator(n):
                yield event
            yield ("end", n.getName())
        else:
            yield ("term", n)

def _make_parser():
    """Create the search string parser."""
    from pyparsing import Word, Group, alphanums, alphas8bit, Forward, Suppress, Keyword, OneOrMore

    query = Forward()

    term = Word(alphas8bit+alphanums+"-.!?,;$&%/").setResultsName("term")

    terms = Forward()
    terms << ((term + terms) | term)

    quotes = Group(
        (Suppress('"') + terms + Suppress('"')) | (Suppress("'") + terms + Suppress("'"))
    ).setResultsName("quotes") | term

    parens = Group(
        Suppress("(") + query + Suppress(")")
    ).setResultsName("group") | quotes

    not_ = Group(Suppress("-") + parens).setResultsName("not") | parens

    fieldname = Word(alphanums + "_")
    field = Group(
        Group(fieldname).setResultsName("fieldname") + Suppress(":") + not_
    ).setResultsName("field") | not_

    or_ = Group(
        field + Suppress(Keyword("or")) + query
    ).setResultsName("or") | field

    query << OneOrMore(or_).setResultsName("query")
    
    return query.parseString
    
_parser = _make_parser()
