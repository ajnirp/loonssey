import datetime

def snake_case_to_title_case(s):
    s = s.title()
    s = s.split('_')
    s = ' '.join(s)
    return s

def parse_timestamp(ts):
    return datetime.datetime.utcfromtimestamp(
        int(ts)).strftime('%-d %b %Y')

def truncate(s):
    NAME_LENGTH_LIMIT = 47
    if len(s) < NAME_LENGTH_LIMIT:
        return s
    else:
        return s[:NAME_LENGTH_LIMIT] + '...'