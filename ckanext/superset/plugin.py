import logging
from ckan import plugins
from ckan.config.declaration import Declaration, Key
from ckan.plugins import toolkit
from ckanext.superset.blueprints.superset import superset_bp
from ckanext.superset.blueprints.images import superset_images_bp
from ckanext.superset.actions import superset_dataset as superset_dataset_actions
from ckanext.superset.auth import superset_dataset as superset_dataset_auth
from ckanext.superset.actions import superset_database as superset_database_actions
from ckanext.superset.auth import superset_database as superset_database_auth


log = logging.getLogger(__name__)


class SupersetPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IConfigDeclaration)
    plugins.implements(plugins.IConfigurer)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "superset")

    # IConfigDeclaration

    def declare_config_options(self, declaration: Declaration, key: Key):

        declaration.annotate("superset")
        group = key.ckanext.superset
        declaration.declare(group.instance.url, "https://test.superset.com")
        declaration.declare(group.instance.user, "test_user")
        declaration.declare(group.instance["pass"], "test_pass")
        declaration.declare(group.instance.provider, "db")
        declaration.declare_bool(group.instance.refresh, True)
        declaration.declare(group.proxy.url, "")
        declaration.declare_int(group.proxy.port, 3128)
        declaration.declare(group.proxy.user, "")
        declaration.declare(group.proxy["pass"], "")

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
    def get_blueprint(self):
        return [
            superset_bp,
            superset_images_bp,
        ]
