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
from ckanext.superset.data import sync as sync_module
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

        # Crear el recurso asociado
        try:
            csv_data = superset_chart.get_chart_csv()
        except (SupersetRequestException, Exception) as e:
            log.error(f"Failed to download CSV for chart {chart_id}: {e}")
            tk.h.flash_success("Dataset created successfully, but the CSV file could not be downloaded from Superset. "
                               "You can try to re-sync later.")
            url = tk.h.url_for('dataset.read', id=pkg['name'])
            return tk.redirect_to(url)

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

        # Mensaje de éxito
        tk.h.flash_success("Dataset created successfully and added to the selected groups.")

        # Redirigir al nuevo dataset
        log.info(f"Dataset {pkg['id']} created with chart_id {chart_id}")

        # redirect to the new CKAN dataset
        url = tk.h.url_for('dataset.read', id=pkg['name'])
        return tk.redirect_to(url)


@superset_bp.route('/update-dataset/<string:chart_id>', methods=['POST'])
def update_dataset(chart_id):
    """ Re-sync the CKAN dataset's CSV resource from its Superset chart.

    Open to anyone with `package_update` rights on the linked dataset
    (creator and org editors), not only sysadmins.
    """
    if not current_user or not current_user.is_authenticated:
        tk.abort(403, "Login required")

    pkgs = tk.get_action('package_search')(
        {'ignore_auth': True},
        {
            'fq': f'{sync_module.EXTRA_CHART_ID}:{chart_id}',
            'include_private': True,
            'include_drafts': True,
        },
    )
    if pkgs.get('count', 0) == 0:
        tk.abort(404, f"CKAN Dataset not found for chart {chart_id}")
    ckan_dataset = pkgs['results'][0]

    context = {'user': current_user.name}
    try:
        tk.check_access('package_update', context, {'id': ckan_dataset['id']})
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized to update this dataset")

    result = sync_module.sync_dataset(ckan_dataset['id'], context=context)
    if result['status'] == 'ok':
        tk.h.flash_success("CSV resource updated successfully.")
    else:
        tk.h.flash_error(f"Sync failed: {result['error']}")

    url = tk.h.url_for('dataset.read', id=ckan_dataset['name'])
    return tk.redirect_to(url)


@superset_bp.route('/sync-settings/<string:package_id>', methods=['GET', 'POST'])
def sync_settings(package_id):
    """ Manage periodic sync settings for a Superset-linked dataset. """
    if not current_user or not current_user.is_authenticated:
        tk.abort(403, "Login required")

    context = {'user': current_user.name}
    try:
        package = tk.get_action('package_show')(context, {'id': package_id})
    except tk.ObjectNotFound:
        tk.abort(404, "Dataset not found")

    if not sync_module.get_extra(package, sync_module.EXTRA_CHART_ID):
        tk.abort(400, "This dataset is not linked to a Superset chart")

    try:
        tk.check_access('package_update', context, {'id': package_id})
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized to update this dataset")

    if request.method == 'POST':
        frequency = request.form.get('frequency', sync_module.FREQUENCY_NONE)
        enabled = request.form.get('enabled') == 'on'
        try:
            sync_module.update_sync_settings(package_id, frequency, enabled, context)
        except tk.ValidationError as e:
            tk.h.flash_error(f"Invalid settings: {e.error_dict}")
            return tk.redirect_to(
                tk.h.url_for('superset_blueprint.sync_settings', package_id=package_id)
            )
        tk.h.flash_success("Sync settings updated.")
        return tk.redirect_to(tk.h.url_for('dataset.read', id=package['name']))

    extra_vars = {
        'pkg_dict': package,
        'dataset_type': package.get('type') or 'dataset',
        'frequency': sync_module.get_extra(package, sync_module.EXTRA_FREQUENCY) or sync_module.FREQUENCY_NONE,
        'enabled': sync_module.get_extra(package, sync_module.EXTRA_ENABLED) == 'true',
        'last_sync': sync_module.get_extra(package, sync_module.EXTRA_LAST_SYNC),
        'last_status': sync_module.get_extra(package, sync_module.EXTRA_LAST_STATUS),
        'last_error': sync_module.get_extra(package, sync_module.EXTRA_LAST_ERROR),
        'next_sync': sync_module.get_extra(package, sync_module.EXTRA_NEXT_SYNC),
        'frequency_choices': [
            (sync_module.FREQUENCY_NONE, tk._('No sync')),
            (sync_module.FREQUENCY_DAILY, tk._('Daily')),
            (sync_module.FREQUENCY_WEEKLY, tk._('Weekly')),
            (sync_module.FREQUENCY_MONTHLY, tk._('Monthly')),
        ],
    }
    return tk.render('superset/sync-settings.html', extra_vars)


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
