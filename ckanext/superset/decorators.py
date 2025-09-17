import logging
from functools import wraps
from ckan.plugins import toolkit

log = logging.getLogger(__name__)


def require_sysadmin_user(func):
    '''
    Decorator for flask view functions. Returns 403 response if no user is logged in or if the login user is not sysadmin.
    '''

    @wraps(func)
    def view_wrapper(*args, **kwargs):
        user = toolkit.current_user

        if not user:
            return toolkit.abort(403, "Forbidden: No user detected")

        # AttributeError: 'AnonymousUser' object has no attribute 'sysadmin'
        if not user.is_authenticated:
            return toolkit.abort(403, "Forbidden: No logged in user detected")

        if not user.sysadmin:
            return toolkit.abort(403, "Sysadmin user required")

        return func(*args, **kwargs)

    return view_wrapper
