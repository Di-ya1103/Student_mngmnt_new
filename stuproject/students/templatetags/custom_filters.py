from django import template

register = template.Library()

@register.filter
def lookup(value, key):
    try:
        return value.get(str(key)) if isinstance(value, dict) else None
    except (TypeError, KeyError):
        return None