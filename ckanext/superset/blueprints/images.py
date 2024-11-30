import logging
from flask import Blueprint
from flask import send_file

from ckanext.superset.config import get_config
from ckanext.superset.decorators import require_sysadmin_user
from ckanext.superset.data.main import SupersetCKAN
from ckanext.superset.data.chart import SupersetChart


log = logging.getLogger(__name__)
superset_images_bp = Blueprint('superset_images', __name__, url_prefix='/superset-images')


@superset_images_bp.route('/chart/<int:chart_id>', methods=['GET'])
@require_sysadmin_user
def chart_image(chart_id):
    """ Expose a supersrt chart thumbnail as an image """

    cfg = get_config()
    sc = SupersetCKAN(**cfg)
    chart = SupersetChart(superset_instance=sc)
    chart.get_from_superset(chart_id)
    thumbnail = chart.get_thumbnail()
    if not thumbnail:
        return f"Thumbnail not found for chart {chart_id}", 404

    # drop the image content to be used externally
    return send_file(thumbnail, mimetype='image/png')
