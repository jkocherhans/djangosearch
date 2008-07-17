from django.conf import settings

def get_summary_length(default=40):
    """
    Gets the summary length in words as specified by the SEARCH_SUMMARY_LENGTH 
    setting, or falls back to default.
    """
    if hasattr(settings, "SEARCH_SUMMARY_LENGTH"):
        return settings.SEARCH_SUMMARY_LENGTH
    return default
