from flask import Blueprint
from ckan.plugins.toolkit import config, render

from ckanext.superset.config import get_config
from ckanext.superset.decorators import require_sysadmin_user
from ckanext.superset.data.main import SupersetCKAN


superset_bp = Blueprint('superset_blueprint', __name__, url_prefix='/apache-superset')


@superset_bp.route('/')
@require_sysadmin_user
def index():
    # Datos informativos
    superset_url = config.get('ckanext.superset.instance.url')
    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    sc.load_datasets()
    datasets_count = sc.datasets_response.get('count', 'ERROR')
    datasets = sc.datasets
    databases_count = 0

    extra_vars = {
        'superset_url': superset_url,
        'datasets_count': datasets_count,
        'datasets': datasets,
        'databases_count': databases_count,
    }
    return render('superset/index.html', extra_vars)
