import logging
from ckan import plugins
from ckan.plugins import toolkit


log = logging.getLogger(__name__)


class SupersetPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "superset")
