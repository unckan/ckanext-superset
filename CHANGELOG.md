# Next release

# 0.2.1 2025-09-17

- Fix missing name when updating Superset resource [#42](https://github.com/unckan/ckanext-superset/pull/42)

# 0.2.0

- Add tests for CKAN 2.11 [#35](https://github.com/unckan/ckanext-superset/pull/35)
- Add groups to new datasets [#31](https://github.com/unckan/ckanext-superset/pull/31)
- Add error logging to Superset [#34](https://github.com/unckan/ckanext-superset/pull/34)

# 0.1.9

Bug fix:
 - Add missing `public` folder.

# 0.1.8

Features:
 - Move to https 0.28.0 droping the proxies parameter [#14](https://github.com/unckan/ckanext-superset/pull/14)
 - Add databases list in admin [#21](https://github.com/unckan/ckanext-superset/pull/21)
 - Add datasets list in admin [#22] (https://github.com/unckan/ckanext-superset/pull/22)
 - Re-sync CSV resources for existing CKAN datasets [#23](https://github.com/unckan/ckanext-superset/pull/23)
 - Add log.critical(error) [#25](https://github.com/unckan/ckanext-superset/pull/25)

# 0.1.7

Features:
 - Move from Superset datasets to Charts [#15](https://github.com/unckan/ckanext-superset/pull/15)
 - Define extra data to CKAN datasets to allow connect them [#16](https://github.com/unckan/ckanext-superset/pull/16)

# 0.1.6

Bug fix:
 - Pin to httpx==0.27.2 to avoid breaking changes in httpx 0.28.0 [#13](https://github.com/unckan/ckanext-superset/pull/13).

# 0.1.5

Features:
 - Allow creating CKAN dataset with resource for Superset [#10](https://github.com/unckan/ckanext-superset/pull/10).

# 0.1.4

Features:

 - New API endpoint at `/api/action/superset_database_list` to get data from Superset URL at `/api/v1/database/`
  [#2](https://github.com/unckan/ckanext-superset/pull/2)
 - Superset admin tab [#6] (https://github.com/unckan/ckanext-superset/pull/6)
 - Datasets list [#7] (https://github.com/unckan/ckanext-superset/pull/7)
 - Databases list [#8] (https://github.com/unckan/ckanext-superset/pull/8)

# 0.1.3

Features:

 - New API endpoint at `/api/action/superset_dataset_list` to get data from Superset URL at `/api/v1/datasets/`
   [#1](https://github.com/unckan/ckanext-superset/pull/1)
