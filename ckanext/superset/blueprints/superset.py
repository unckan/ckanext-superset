from flask import Blueprint
from ckan.plugins.toolkit import config, render
from ckanext.api_tracking.decorators import require_sysadmin_user


superset_bp = Blueprint('superset_blueprint', __name__, url_prefix='/apache-superset')


@superset_bp.route('/')
@require_sysadmin_user
def index():
    # Datos informativos
    superset_url = config.get('ckanext.superset.instance.url')
    datasets_count = 3
    databases_count = 5

    extra_vars = {
        'superset_url': superset_url,
        'datasets_count': datasets_count,
        'databases_count': databases_count,
        'active': 'superset-dashboard',
    }
    return render('superset/index.html', extra_vars)
