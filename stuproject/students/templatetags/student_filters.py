# students/templatetags/student_filters.py
from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    return dictionary.get(str(key), '')