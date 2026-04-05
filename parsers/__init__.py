import config
from parsers.robinhood import parse_robinhood_email_stories

_EMAIL_STORY_PARSERS = {
    "robinhood": parse_robinhood_email_stories,
}


def get_specialized_parser_name(email):
    sender = email.get("from") or ""
    for pattern, parser_name in config.CONTENT_PARSER_SENDER_RULES:
        if pattern.search(sender):
            return parser_name
    return None


def parse_specialized_email_stories(email):
    parser_name = get_specialized_parser_name(email)
    if not parser_name:
        return []

    parser = _EMAIL_STORY_PARSERS.get(parser_name)
    if parser is None:
        raise ValueError(f"Unknown email story parser configured: {parser_name}")

    return parser(email)
