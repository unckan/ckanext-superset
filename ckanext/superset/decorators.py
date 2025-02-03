from functools import wraps
from ckan.plugins import toolkit


def require_sysadmin_user(func):
    '''
    Decorator for flask view functions. Returns 403 response if no user is logged in or if the login user is not sysadmin.
    '''

    @wraps(func)
    def view_wrapper(*args, **kwargs):
        user_name = getattr(toolkit.c, "user", None)
        print(f"\n🔍 Usuario detectado en CKAN: {user_name}")

        if not user_name:
            print("⛔ No se detectó un usuario autenticado.")
            return toolkit.abort(403, "Forbidden: No user detected")

        try:
            user_data = toolkit.get_action('user_show')({}, {'id': user_name})
            print(f"👤 Datos del usuario recuperados: {user_data}")
        except Exception as e:
            print(f"❌ Error al obtener datos del usuario: {e}")
            return toolkit.abort(403, "Forbidden: User not found")

        if not user_data.get('sysadmin', False):
            print("⛔ Usuario no tiene permisos de sysadmin.")
            return toolkit.abort(403, "Sysadmin user required")

        print("✅ Usuario autenticado correctamente como sysadmin.")
        return func(*args, **kwargs)

    return view_wrapper
