import logging
import tempfile
from flask import Blueprint
from werkzeug.datastructures import FileStorage
from ckan import model
from ckan.common import current_user, request
from ckan.plugins import toolkit as tk

from ckanext.superset.config import get_config
from ckanext.superset.decorators import require_sysadmin_user
from ckanext.superset.data.main import SupersetCKAN
from ckanext.superset.exceptions import SupersetRequestException
from ckanext.superset.utils import slug


log = logging.getLogger(__name__)
superset_bp = Blueprint('superset_blueprint', __name__, url_prefix='/apache-superset')


@superset_bp.route('/', methods=['GET'])
@require_sysadmin_user
def index():
    # Datos informativos
    superset_url = tk.config.get('ckanext.superset.instance.url')
    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    sc.load_charts()
    charts_count = sc.charts_response.get('count', 'ERROR')
    charts = sc.charts

    extra_vars = {
        'superset_url': superset_url,
        'charts_count': charts_count,
        'charts': charts,
    }
    return tk.render('superset/index.html', extra_vars)


@superset_bp.route('/create-dataset/<string:chart_id>', methods=['GET', 'POST'])
@require_sysadmin_user
def create_dataset(chart_id):
    """ Create a new CKAN dataset from a Superset dataset """

    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    superset_chart = sc.get_chart(chart_id)
    if request.method == 'GET':

        extra_vars = {
            'superset_chart': superset_chart,
        }
        return tk.render('superset/create-dataset.html', extra_vars)

    if request.method == 'POST':
        # Create the dataset
        ckan_dataset_title = request.form.get('ckan_dataset_title')
        # generate a slug name
        ckan_dataset_name = slug(ckan_dataset_title)
        # ensure the name is unique
        c = 2
        while pkg := model.Session.query(model.Package).filter(model.Package.name == ckan_dataset_name).first():
            log.warning(f'Package name {ckan_dataset_name} already exists for package {pkg.id}')
            ckan_dataset_name = f'{slug(ckan_dataset_title)}-{chart_id}-{c}'
            c += 1

        # Create the dataset
        action = tk.get_action("package_create")
        context = {'user': current_user.name}
        data = {
            'name': ckan_dataset_name,
            'title': ckan_dataset_title,
            'notes': request.form.get('ckan_dataset_notes'),
            'owner_org': request.form.get('ckan_organization_id'),
            'private': request.form.get('ckan_dataset_private'),
            'extras': [
                {'key': 'superset_chart_id', 'value': chart_id},
            ],
        }
        pkg = action(context, data)
        # Create the resource
        try:
            csv_data = superset_chart.get_chart_csv()
        except SupersetRequestException as e:
            tk.abort(500, f"Superset Error getting CSV data {e}")
        except Exception as e:
            tk.abort(500, f"Unknown Error getting CSV data {e}")

        resource_name = request.form.get('ckan_dataset_resource_name')
        f = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
        f.write(csv_data)
        f.close()
        upload_file = FileStorage(filename=resource_name, stream=open(f.name, 'rb'))
        action = tk.get_action("resource_create")
        context = {'user': current_user.name}
        data = {
            'package_id': pkg['id'],
            'upload': upload_file,
            'url_type': 'upload',
            'format': 'csv',
            'name': resource_name,
        }
        action(context, data)

        # Add a flask message
        tk.h.flash_success("Dataset created successfully.")

        # redirect to the new CKAN dataset
        url = tk.h.url_for('dataset.read', id=pkg['name'])
        return tk.redirect_to(url)


@superset_bp.route('/update-dataset/<string:chart_id>', methods=['POST'])
@require_sysadmin_user
def update_dataset(chart_id):
    """ Update the CKAN dataset just with the CSV data from the Superset chart """

    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    superset_chart = sc.get_chart(chart_id)

    # Get/check the dataset previously imported
    ckan_dataset = superset_chart.ckan_dataset
    if not ckan_dataset:
        tk.abort(404, f"CKAN Dataset not found for chart {chart_id}")

    resources = ckan_dataset.get('resources', [])
    if not resources:
        tk.abort(400, f"CKAN Dataset from chart {chart_id} do not have resources")
    elif len(resources) > 1:
        tk.abort(400, f"CKAN Dataset from chart {chart_id} have more than one resource")

    resource = resources[0]

    # Update the resource
    try:
        csv_data = superset_chart.get_chart_csv()
    except SupersetRequestException as e:
        tk.abort(500, f"Superset Error getting CSV data {e}")
    except Exception as e:
        tk.abort(500, f"Unknown Error getting CSV data {e}")

    resource_name = request.form.get('ckan_dataset_resource_name')
    f = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
    f.write(csv_data)
    f.close()
    upload_file = FileStorage(filename=resource_name, stream=open(f.name, 'rb'))
    action = tk.get_action("resource_patch")
    context = {'user': current_user.name}
    data = {'id': resource['id'], 'upload': upload_file}
    action(context, data)

    # Add a flask message
    tk.h.flash_success("CSV resource updated successfully.")
    # redirect to the updated CKAN dataset
    url = tk.h.url_for('dataset.read', id=ckan_dataset['name'])
    return tk.redirect_to(url)


@superset_bp.route('/list_databases', methods=['GET'])
@require_sysadmin_user
def list_databases():
    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    superset_databases = sc.get_databases()
    superset_url = tk.config.get('ckanext.superset.instance.url')
    extra_vars = {
        'databases': superset_databases,
        'superset_url': superset_url,
    }
    return tk.render('superset/databases_list.html', extra_vars)


@superset_bp.route('/datasets', methods=['GET'])
@require_sysadmin_user
def list_datasets():
    """ List all datasets created from Superset charts """
    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    sc.load_datasets()

    # Verifica la respuesta inicial
    print("Datasets Response:", sc.datasets_response)

    dataset_ids = sc.datasets_response.get('ids', [])
    dataset_ids = dataset_ids[-2:]  # Solo los últimos 10 datasets
    raw_datasets = sc.get_list_datasets(dataset_ids)
    # enviar solo los ultimo 10 datasets
    raw_datasets = raw_datasets[-2:]
    print("Raw Datasets:", raw_datasets)

    # Procesa los datos para aplanarlos
    datasets = [
        {
            'table_name': d['data'].get('table_name', 'Sin nombre') if d and 'data' in d else 'Sin nombre',
            'description': d['data'].get('description', 'Sin descripción') if d and 'data' in d else 'Sin descripción',
            'database_name': {d['data'].get('database', {}).get('database_name', 'Sin organización')
                              if d and 'data' in d else 'Sin organización'},
            'superset_chart_id': d['data'].get('id') if d and 'data' in d else None,
            'private': False,  # Ajustar esta lógica si hay un indicador de privacidad
        }
        for d in raw_datasets if d is not None
    ]

    # Verifica los datos después de procesarlos
    print("Processed Datasets:", datasets)

    superset_url = tk.config.get('ckanext.superset.instance.url')
    extra_vars = {
        'datasets': datasets,
        'superset_url': superset_url,
    }
    return tk.render('superset/list-datasets.html', extra_vars)
