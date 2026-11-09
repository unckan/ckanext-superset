"""
Turn Superset failures into a proper error page instead of a raw 500.

The details of the failure are already logged by
`SupersetCKAN.handle_error` (and pushed by push-errors), here we only answer
the user with a clear message and a gateway status code
(502 Bad Gateway / 504 Gateway Timeout).
"""
import logging

from ckan.plugins import toolkit as tk

from ckanext.superset.exceptions import SupersetRequestException


log = logging.getLogger(__name__)


def _status_code(error):
    return getattr(error, 'status_code', None) or 502


def _message(status_code):
    if status_code == 504:
        return tk._('Apache Superset is taking too long to respond. Please try again later.')
    return tk._('Apache Superset is not available right now. Please try again later.')


def superset_error_page(error):
    """ Render CKAN's error page for a failed Superset request """
    status_code = _status_code(error)
    log.warning(f"Superset request failed ({status_code}): {error}")
    extra_vars = {
        'code': status_code,
        'name': 'Gateway Timeout' if status_code == 504 else 'Bad Gateway',
        'content': _message(status_code),
    }
    return tk.render('error_document_template.html', extra_vars), status_code


def superset_error_text(error):
    """ Plain text answer, for endpoints that are not HTML pages (images) """
    status_code = _status_code(error)
    log.warning(f"Superset request failed ({status_code}): {error}")
    return _message(status_code), status_code, {'Content-Type': 'text/plain; charset=utf-8'}


def register_superset_error_handler(blueprint, handler=superset_error_page):
    blueprint.register_error_handler(SupersetRequestException, handler)
