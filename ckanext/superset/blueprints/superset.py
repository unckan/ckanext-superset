from flask import Blueprint
from ckan.plugins.toolkit import render
from ckanext.stats import stats as stats_lib
from ckanext.api_tracking.decorators import require_sysadmin_user

superset = Blueprint(
    'superset_dashboard', __name__, url_prefix='/superset-dashboard'
)


@superset.route('/')
@require_sysadmin_user
def index():
    # Datos informativos
    superset_url = 'http://superset.ckan.local'
    datasets_count = stats_lib.Stats().get_num_packages_total()
    databases_count = stats_lib.Stats().get_num_datasets()

    extra_vars = {
        'superset_url': superset_url,
        'datasets_count': datasets_count,
        'databases_count': databases_count,
        'active': 'superset-dashboard',
    }
    return render('dashboard/superset-dashboard.html', extra_vars)
