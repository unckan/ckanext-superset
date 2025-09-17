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

    # Obtener los grupos disponibles
    groups_available = tk.get_action('group_list')({'user': current_user.name}, {'all_fields': True})

    if request.method == 'GET':
        extra_vars = {
            'superset_chart': superset_chart,
            'groups_available': groups_available,
        }
        return tk.render('superset/create-dataset.html', extra_vars)

    if request.method == 'POST':
        # Crear el dataset
        ckan_dataset_title = request.form.get('ckan_dataset_title')
        # Generar un slug para el nombre
        ckan_dataset_name = slug(ckan_dataset_title)

        # Asegurar que el nombre sea único
        c = 2
        while pkg := model.Session.query(model.Package).filter(model.Package.name == ckan_dataset_name).first():
            log.warning(f'Package name {ckan_dataset_name} already exists for package {pkg.id}')
            ckan_dataset_name = f'{slug(ckan_dataset_title)}-{chart_id}-{c}'
            c += 1

        # Obtener los grupos seleccionados del formulario
        selected_group_ids = request.form.getlist('ckan_group_ids[]')

        # Validar los IDs seleccionados
        valid_group_ids = [group['id'] for group in groups_available]
        invalid_groups = [group_id for group_id in selected_group_ids if group_id not in valid_group_ids]

        if invalid_groups:
            raise tk.ValidationError(f"Invalid group IDs: {', '.join(invalid_groups)}")

        # Crear el dataset
        action = tk.get_action("package_create")
        context = {'user': current_user.name}
        data = {
            'name': ckan_dataset_name,
            'title': ckan_dataset_title,
            'notes': request.form.get('ckan_dataset_notes'),
            'owner_org': request.form.get('ckan_organization_id'),
            'private': request.form.get('ckan_dataset_private') == 'on',
            'extras': [{'key': 'superset_chart_id', 'value': chart_id}],
            'groups': [{"id": group_id} for group_id in selected_group_ids],
        }
        pkg = action(context, data)

        # Crear el recurso asociado
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

        # Asociar el dataset a los grupos seleccionados
        for group_id in selected_group_ids:
            tk.get_action('member_create')(
                {'user': current_user.name},
                {
                    'id': group_id,  # ID del grupo
                    'object': pkg['id'],  # ID del dataset
                    'object_type': 'package',  # Siempre 'package' para datasets
                    'capacity': 'member'  # Rol estándar
                }
            )

        # Mensaje de éxito
        tk.h.flash_success("Dataset created successfully and added to the selected groups.")

        # Redirigir al nuevo dataset
        log.info(f"Dataset {pkg['id']} created with chart_id {chart_id}")

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
    if not superset_chart:
        error = f"Superset chart not found for chart_id {chart_id}"
        log.error(error)
        tk.abort(404, error)

    # Get/check the dataset previously imported
    ckan_dataset = superset_chart.ckan_dataset
    if not ckan_dataset:
        log.error(f"No dataset found for chart_id {chart_id}. Superset chart: {superset_chart}")
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

    resource_name = resource.get('name')
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
    # Obtener los datasets de Superset
    datasets = sc.get_datasets()
    superset_url = tk.config.get('ckanext.superset.instance.url')
    extra_vars = {
        'datasets': datasets,
        'superset_url': superset_url,
    }
    return tk.render('superset/list-datasets.html', extra_vars)
