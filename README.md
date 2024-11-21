[![Tests](https://github.com/unckan/ckanext-superset/actions/workflows/test-superset-extension.yml/badge.svg?branch=main)](https://github.com/unckan/ckanext-superset/actions)

# CKAN Apache Superset extension

CKAN extension to connect an Apache Superset instance to CKAN.  

![Apache admin tab](/docs/images/admin-tab-view.png)

![Apache admin](/docs/images/admin-view.png)

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.10            | Yes           |
| 2.11            | not tested    |


## Config settings

### Apache Superset instance

ckanext.superset.instance.url = http://superset:8088  
ckanext.superset.instance.user = admin  
ckanext.superset.instance.pass = admin  
ckanext.superset.instance.provider = db  
ckanext.superset.instance.refresh = true  

### Proxy (only if needed)

ckanext.superset.proxy.url = http://superset:8088  
ckanext.superset.proxy.port = 3128  
ckanext.superset.proxy.user = admin@example.com  
ckanext.superset.proxy.pass = pass  


## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
