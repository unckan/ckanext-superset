import logging
from ckan import model
from ckanext.superset.utils import slug


log = logging.getLogger(__name__)


def prepare_data_import(chart_id, request, groups_available):
    """ Prepare and validate the data from the POST request
        Return data|None, error|None
    """
    # Validar antes de crear el/los datasets
    # Obtener los grupos seleccionados del formulario
    selected_group_ids = request.form.getlist('ckan_group_ids[]')
    # Validar los IDs seleccionados
    valid_group_ids = [group['id'] for group in groups_available]
    invalid_groups = [group_id for group_id in selected_group_ids if group_id not in valid_group_ids]
    if invalid_groups:
        error = f"Invalid group IDs: {', '.join(invalid_groups)}"
        return None, (200, error)

    # Check if we need to split dataset or resources
    ckan_dataset_split = request.form.get('ckan_dataset_split')
    if ckan_dataset_split:
        split_datasets = ckan_dataset_split.startswith('dataset_')
        split_resources = ckan_dataset_split.startswith('resource_')
    # Create the dataset
    ckan_dataset_title = request.form.get('ckan_dataset_title')
    # Generar un slug para el nombre
    ckan_dataset_name = slug(ckan_dataset_title)

    data = {
        'chart_id': chart_id,
        'name': ckan_dataset_name,
        'title': ckan_dataset_title,
        'notes': request.form.get('ckan_dataset_notes'),
        'owner_org': request.form.get('ckan_organization_id'),
        'private': request.form.get('ckan_dataset_private') == 'on',
        'extras': [{'key': 'superset_chart_id', 'value': chart_id}],
        'groups': [{"id": group_id} for group_id in selected_group_ids],
        'resource_name': request.form.get('ckan_dataset_resource_name'),
        'split_datasets': split_datasets,
        'split_resources': split_resources,
    }
    return data, None


def import_datasets(context, data):
    """ Create one or more basic datasets improting them
        Returns a list of dataset ids
    """
    response = []
    # Asegurar que el nombre sea único
    c = 2
    while pkg := model.Session.query(model.Package).filter(model.Package.name == ckan_dataset_name).first():
        log.warning(f'Package name {ckan_dataset_name} already exists for package {pkg.id}')
        ckan_dataset_name = f'{slug(ckan_dataset_title)}-{chart_id}-{c}'
        c += 1

    # Crear el dataset
    action = tk.get_action("package_create")

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