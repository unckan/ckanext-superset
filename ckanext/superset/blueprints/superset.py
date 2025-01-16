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
    # Date the Superset URL from the config
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

    # get the available groups

    groups_available = tk.get_action('group_list')({'user': current_user.name}, {'all_fields': True})

    # Get available Tags for each chart
    tags_available = tk.get_action('tag_list')({'user': current_user.name}, {'all_fields': True})
    # Format tags to display readable names
    formatted_tags = [{"id": tag["id"], "name": tag["name"]} for tag in tags_available]

    if not tags_available:
        log.warning(f"No tags found for chart {superset_chart.data.get('slice_name', 'unknown')}")

    # Sort groups and tags by name
    groups_available = sorted(groups_available, key=lambda g: g['name'])
    formatted_tags = sorted(formatted_tags, key=lambda t: t['name'])

    if request.method == 'GET':
        extra_vars = {
            'superset_chart': superset_chart,
            'groups_available': groups_available,
            'tags_available': formatted_tags,
        }
        return tk.render('superset/create-dataset.html', extra_vars)

    if request.method == 'POST':
        # Create the dataset
        ckan_dataset_title = request.form.get('ckan_dataset_title')
        # Generate a slug for the name
        ckan_dataset_name = slug(ckan_dataset_title)

        # Ensure the name is unique
        c = 2
        while pkg := model.Session.query(model.Package).filter(model.Package.name == ckan_dataset_name).first():
            log.warning(f'Package name {ckan_dataset_name} already exists for package {pkg.id}')
            ckan_dataset_name = f'{slug(ckan_dataset_title)}-{chart_id}-{c}'
            c += 1

        # Get the selected groups from the form
        selected_group_ids = request.form.getlist('ckan_group_ids[]')

        # Validate the selected IDs
        valid_group_ids = [group['id'] for group in groups_available]
        invalid_groups = [group_id for group_id in selected_group_ids if group_id not in valid_group_ids]

        if invalid_groups:
            raise tk.ValidationError(f"Invalid group IDs: {', '.join(invalid_groups)}")

        # Get the selected Tags from the form
        selected_tags = request.form.getlist('ckan_tags[]')
        # Convert the selected tags to a list of dictionaries
        tags = [{"name": tag} for tag in selected_tags]

        # Validate the tags selected
        if not tags:
            log.warning(f"No valid tags provided for the dataset {ckan_dataset_name}. Tags will be empty.")

        # Create the dataset
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
            'tags': tags,
        }
        pkg = action(context, data)

        # Create the associated resource
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

        # Associate the dataset with the selected groups
        for group_id in selected_group_ids:
            tk.get_action('member_create')(
                {'user': current_user.name},
                {
                    'id': group_id,  # ID from the group
                    'object': pkg['id'],  # ID from the dataset
                    'object_type': 'package',  # Always 'package' for datasets
                    'capacity': 'member'  # Standard role
                }
            )

        # Add a flask message exiting
        tk.h.flash_success("Dataset created successfully and added to the selected groups.")

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
