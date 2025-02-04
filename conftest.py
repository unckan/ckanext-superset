pytest_plugins = [
    u'ckanext.superset.tests.fixtures',
]

import ckan.plugins.toolkit as toolkit

toolkit.config["ckanext.superset.instance.url"] = "https://test.superset.com"
toolkit.config["ckanext.superset.instance.user"] = "test_user"
toolkit.config["ckanext.superset.instance.pass"] = "test_pass"
toolkit.config["ckanext.superset.instance.provider"] = "db"
toolkit.config["ckanext.superset.instance.refresh"] = "true"
