[![Tests](https://github.com/unckan/ckanext-superset/actions/workflows/test-superset-extension.yml/badge.svg?branch=main)](https://github.com/unckan/ckanext-superset/actions)

# CKAN Apache Superset extension

CKAN extension to connect an Apache Superset instance to CKAN.  

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.10            | Yes           |
| 2.11            | not tested    |


## Config settings

### Apache Superset instance

ckanext.superser.instance.url = http://superset:8088
ckanext.superser.instance.user = admin
ckanext.superser.instance.pass = admin
ckanext.superser.instance.provider = db
ckanext.superser.instance.refresh = true

### Proxy (only if needed)

ckanext.superser.proxy.url = http://superset:8088
ckanext.superser.proxy.port = 3128
ckanext.superser.proxy.user = admin@example.com
ckanext.superser.proxy.pass = pass


## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
