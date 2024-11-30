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
            # 'superset_dataset_id': superset_dataset_id,
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

        # redirect to the new CKAN dataset
        url = tk.h.url_for('dataset.read', id=pkg['name'])
        return tk.redirect_to(url)
