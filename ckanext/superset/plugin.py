import logging
from ckan import plugins
from ckan.plugins import toolkit
from ckanext.superset import blueprints
from ckanext.superset.actions import superset_dataset as superset_dataset_actions
from ckanext.superset.auth import superset_dataset as superset_dataset_auth
from ckanext.superset.actions import superset_database as superset_database_actions
from ckanext.superset.auth import superset_database as superset_database_auth


log = logging.getLogger(__name__)


class SupersetPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IConfigurer)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "superset")

    # IActions

    def get_actions(self):
        return {
            "superset_dataset_list": superset_dataset_actions.superset_dataset_list,
            "superset_database_list": superset_database_actions.superset_database_list
        }

    # IAuthFunctions

    def get_auth_functions(self):
        return {
            "superset_dataset_list": superset_dataset_auth.superset_dataset_list,
            "superset_database_list": superset_database_auth.superset_database_list
        }

    # IBlueprint
    def get_blueprints(self):
        return [
            blueprints.superset
        ]
