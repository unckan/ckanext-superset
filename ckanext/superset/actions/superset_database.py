import logging
from ckan.plugins import toolkit
from ckanext.superset.config import get_config
from ckanext.superset.data.main import SupersetCKAN


log = logging.getLogger(__name__)


@toolkit.side_effect_free
def superset_database_list(context, data_dict):
    """ get the /api/v1/database from Superset """

    toolkit.check_access('superset_database_list', context, data_dict)

    # Get the configuration values
    cfg = get_config()
    SC = SupersetCKAN(**cfg)

    return SC.get("database/")
