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
    sc.load_databases()
    databases = sc.databases
    databases_count = len(databases)

    extra_vars = {
        'superset_url': superset_url,
        'datasets_count': datasets_count,
        'datasets': datasets,
        'databases_count': databases_count,
        'databases': databases,
    }
    return render('superset/index.html', extra_vars)


@superset_bp.route('/create-dataset/<string:superset_dataset_id>')
@require_sysadmin_user
def create_dataset(superset_dataset_id):
    """ Create a new CKAN dataset from a Superset dataset """
    # Check if the dataset exists in CKAN
    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    superset_dataset = sc.get_dataset(superset_dataset_id)

    extra_vars = {
        'superset_dataset': superset_dataset,
    }
    return render('superset/create-dataset.html', extra_vars)
