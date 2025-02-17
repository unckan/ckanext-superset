from functools import wraps
from ckan.plugins import toolkit


def require_sysadmin_user(func):
    '''
    Decorator for flask view functions. Returns 403 response if no user is logged in or if the login user is not sysadmin.
    '''

    @wraps(func)
    def view_wrapper(*args, **kwargs):
        user_name = getattr(toolkit.c, "user", None)

        if not user_name:
            return toolkit.abort(403, "Forbidden: No user detected")

        try:
            user_data = toolkit.get_action('user_show')({}, {'id': user_name})
        except Exception as e:
            return toolkit.abort(403, "Forbidden: User not found")

        if not user_data.get('sysadmin', False):
            return toolkit.abort(403, "Sysadmin user required")

        return func(*args, **kwargs)

    return view_wrapper
