import logging
import os
from ckan import plugins
from ckan.config.declaration import Declaration, Key
from ckan.plugins import toolkit
from ckanext.superset.blueprints.superset import superset_bp
from ckanext.superset.blueprints.images import superset_images_bp
from ckanext.superset.actions import superset_dataset as superset_dataset_actions
from ckanext.superset.auth import superset_dataset as superset_dataset_auth
from ckanext.superset.actions import superset_database as superset_database_actions
from ckanext.superset.auth import superset_database as superset_database_auth
from ckanext.superset import cli as superset_cli
from ckanext.superset.data.sync import ACTIVITY_TYPE_SYNC_FAILED


log = logging.getLogger(__name__)


def _register_activity_types():
    """ Register custom activity types in CKAN's activity validators.

    The activity plugin validates `activity_type` against `object_id_validators`;
    unknown types are rejected. We register ours as a package-bound type so the
    object_id is treated as a package ID.
    """
    try:
        from ckanext.activity.logic.validators import object_id_validators
    except ImportError:
        log.info("ckanext.activity not installed; skipping activity type registration")
        return
    object_id_validators[ACTIVITY_TYPE_SYNC_FAILED] = 'package_id_exists'


_register_activity_types()


class SupersetPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IConfigDeclaration)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITranslation)

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
        # pass is a reserved word in python, so we use with _descend
        declaration.declare(group.instance._descend("pass"), "test_pass")
        declaration.declare(group.instance.provider, "db")
        declaration.declare_bool(group.instance.refresh, True)
        declaration.declare(group.proxy.url, "")
        declaration.declare_int(group.proxy.port, 3128)
        declaration.declare(group.proxy.user, "")
        # pass is a reserved word in python, so we use with _descend
        declaration.declare(group.proxy._descend("pass"), "")

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

    # ITranslation

    def i18n_directory(self):
        return os.path.join(os.path.dirname(__file__), "i18n")

    def i18n_domain(self):
        return "ckanext-superset"

    def i18n_locales(self):
        """Lanaguages this plugin has translations for."""
        # Return a list of languages that this plugin has translations for.
        return ["es", "en"]

    # IClick
    def get_commands(self):
        return superset_cli.get_commands()
