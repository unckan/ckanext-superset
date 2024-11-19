"""
Connect to the superset API (through a proxy server if required)
"""
import logging

from ckan.plugins.toolkit import config


log = logging.getLogger(__name__)


def get_config():
    """ Get configuration values for superset and proxy"""
    log.debug("Getting superset configuration values")
    cfg = {
        'superset_url': config.get("ckanext.superser.instance.url").rstrip('/'),
        'superset_user': config.get("ckanext.superser.instance.user"),
        'superset_pass': config.get("ckanext.superser.instance.pass"),
        'superset_provider': config.get("ckanext.superser.instance.provider", "db"),
        'superset_refresh': config.get("ckanext.superser.instance.refresh", "true"),
        'proxy_url': config.get("ckanext.superser.proxy.url"),
        'proxy_port': config.get("ckanext.superser.proxy.port", '3128'),
        'proxy_user': config.get("ckanext.superser.proxy.user"),
        'proxy_pass': config.get("ckanext.superser.proxy.pass"),
    }

    log.info(f'Configuration values: Superset: {cfg["superset_url"]}, Proxy: {cfg.get("proxy_url")}')

    return cfg
