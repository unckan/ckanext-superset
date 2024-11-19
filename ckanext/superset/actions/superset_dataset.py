import logging
from ckan.plugins import toolkit
from ckanext.superset.config import get_config
from ckanext.superset.connect import SupersetCKAN


log = logging.getLogger(__name__)


@toolkit.side_effect_free
def superset_dataset_list(context, data_dict):
    """ get the /api/v1/dataset list from Superset """

    toolkit.check_access('superset_dataset_list', context, data_dict)

    # Get the configuration values
    cfg = get_config()
    SC = SupersetCKAN(**cfg)

    return SC.get("dataset/")
