from django.conf import settings

def get_summary_length(default=40):
    """
    Gets the summary length in words as specified by the SEARCH_SUMMARY_LENGTH 
    setting, or falls back to default.
    """
    if hasattr(settings, "SEARCH_SUMMARY_LENGTH"):
        return settings.SEARCH_SUMMARY_LENGTH
    return default

def slicify(obj, limit=None, offset=None):
    """
    Slices an object according to limit and offset.
    """
    if limit is not None:
        if offset is not None:
            obj = obj[offset:offset+limit]
        else:
            obj = obj[:limit]
    elif offset is not None:
        obj = obj[offset:]
    return obj
    