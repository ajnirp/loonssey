import datetime

def snake_case_to_title_case(s):
    s = s.title()
    s = s.split('_')
    s = ' '.join(s)
    return s

def parse_timestamp(ts):
    return datetime.datetime.utcfromtimestamp(
        int(ts)).strftime('%-d %b %Y')