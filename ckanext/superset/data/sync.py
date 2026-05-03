"""
Periodic sync of CKAN datasets created from Apache Superset charts.

Sync state lives in package extras:
- superset_chart_id          (already used) link to Superset chart
- superset_sync_frequency    'daily' | 'weekly' | 'monthly'
- superset_sync_enabled      'true' | 'false'
- superset_last_sync         ISO-8601 UTC datetime of the last attempt
- superset_last_sync_status  'ok' | 'error'
- superset_last_sync_error   short text (truncated)
- superset_next_sync         ISO-8601 UTC datetime when the next run is due

All defaults are absent: a dataset that has never been configured carries no
sync extras and is invisible to the scheduler.
"""
import logging
import tempfile
from datetime import datetime, timedelta, timezone

from werkzeug.datastructures import FileStorage
from ckan import model
from ckan.plugins import plugin_loaded, toolkit as tk

from ckanext.superset.config import get_config
from ckanext.superset.data.main import SupersetCKAN
from ckanext.superset.exceptions import SupersetRequestException


log = logging.getLogger(__name__)


FREQUENCY_DAILY = 'daily'
FREQUENCY_WEEKLY = 'weekly'
FREQUENCY_MONTHLY = 'monthly'
FREQUENCY_NONE = 'none'

VALID_FREQUENCIES = (FREQUENCY_DAILY, FREQUENCY_WEEKLY, FREQUENCY_MONTHLY, FREQUENCY_NONE)

EXTRA_CHART_ID = 'superset_chart_id'
EXTRA_FREQUENCY = 'superset_sync_frequency'
EXTRA_ENABLED = 'superset_sync_enabled'
EXTRA_LAST_SYNC = 'superset_last_sync'
EXTRA_LAST_STATUS = 'superset_last_sync_status'
EXTRA_LAST_ERROR = 'superset_last_sync_error'
EXTRA_NEXT_SYNC = 'superset_next_sync'

ACTIVITY_TYPE_SYNC_FAILED = 'superset sync failed'

_FREQUENCY_DELTAS = {
    FREQUENCY_DAILY: timedelta(days=1),
    FREQUENCY_WEEKLY: timedelta(days=7),
    FREQUENCY_MONTHLY: timedelta(days=30),
}


def calculate_next_sync(frequency, from_dt=None):
    """ Return the datetime of the next run for a given frequency, or None. """
    delta = _FREQUENCY_DELTAS.get(frequency)
    if delta is None:
        return None
    base = from_dt or datetime.now(timezone.utc)
    return base + delta


def get_extra(package_dict, key, default=None):
    for extra in package_dict.get('extras', []) or []:
        if extra.get('key') == key:
            return extra.get('value')
    return default


def merge_extras(package_dict, updates):
    """ Return a new extras list with `updates` (key->value) merged in.

    A value of None removes the key.
    """
    extras = package_dict.get('extras', []) or []
    by_key = {e['key']: dict(e) for e in extras}
    for key, value in updates.items():
        if value is None:
            by_key.pop(key, None)
        else:
            by_key[key] = {'key': key, 'value': str(value)}
    return list(by_key.values())


def update_sync_settings(package_id, frequency, enabled, context):
    """ Persist user-chosen sync settings on a package.

    Recomputes `superset_next_sync` so the scheduler picks it up (or stops
    picking it up) immediately.
    """
    if frequency not in VALID_FREQUENCIES:
        raise tk.ValidationError({'frequency': [f'Invalid frequency: {frequency}']})

    package = tk.get_action('package_show')(context, {'id': package_id})

    if enabled and frequency != FREQUENCY_NONE:
        next_sync = calculate_next_sync(frequency)
    else:
        next_sync = None

    updates = {
        EXTRA_FREQUENCY: frequency if frequency != FREQUENCY_NONE else None,
        EXTRA_ENABLED: 'true' if enabled else 'false',
        EXTRA_NEXT_SYNC: next_sync.isoformat() if next_sync else None,
    }

    new_extras = merge_extras(package, updates)
    tk.get_action('package_patch')(
        context, {'id': package_id, 'extras': new_extras}
    )
    return {'frequency': frequency, 'enabled': enabled, 'next_sync': next_sync}


def sync_dataset(package_id, context=None):
    """ Pull the latest CSV from Superset and replace the dataset's resource.

    Records the outcome on the package extras and recomputes `next_sync` based
    on the package's current frequency setting.
    """
    if context is None:
        site_user = tk.get_action('get_site_user')({'ignore_auth': True}, {})
        ctx = {'ignore_auth': True, 'user': site_user['name']}
    else:
        ctx = context
    package = tk.get_action('package_show')(ctx, {'id': package_id})

    chart_id = get_extra(package, EXTRA_CHART_ID)
    if not chart_id:
        return _record_result(package, status='error', error='No superset_chart_id extra')

    resources = package.get('resources', []) or []
    if not resources:
        return _record_result(package, status='error', error='Dataset has no resources')
    if len(resources) > 1:
        return _record_result(package, status='error', error='Dataset has more than one resource')
    resource = resources[0]

    try:
        cfg = get_config()
        sc = SupersetCKAN(**cfg)
        chart = sc.get_chart(chart_id)
        csv_data = chart.get_chart_csv()
    except SupersetRequestException as e:
        log.error(f"Superset error syncing chart {chart_id}: {e}")
        return _record_result(package, status='error', error=str(e))
    except Exception as e:
        log.exception(f"Unexpected error syncing chart {chart_id}")
        return _record_result(package, status='error', error=str(e))

    f = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
    f.write(csv_data)
    f.close()
    upload_file = FileStorage(filename=resource.get('name'), stream=open(f.name, 'rb'))
    try:
        tk.get_action('resource_patch')(
            ctx, {'id': resource['id'], 'upload': upload_file}
        )
    except Exception as e:
        log.exception(f"resource_patch failed for {resource['id']}")
        return _record_result(package, status='error', error=str(e))

    return _record_result(package, status='ok', error=None)


def _record_result(package_dict, status, error):
    """ Persist the outcome of a sync attempt to the package extras. """
    now = datetime.now(timezone.utc)
    frequency = get_extra(package_dict, EXTRA_FREQUENCY)
    enabled = get_extra(package_dict, EXTRA_ENABLED) == 'true'
    next_sync = calculate_next_sync(frequency, from_dt=now) if enabled else None

    updates = {
        EXTRA_LAST_SYNC: now.isoformat(),
        EXTRA_LAST_STATUS: status,
        EXTRA_LAST_ERROR: error[:500] if error else None,
        EXTRA_NEXT_SYNC: next_sync.isoformat() if next_sync else None,
    }
    new_extras = merge_extras(package_dict, updates)
    site_user = tk.get_action('get_site_user')({'ignore_auth': True}, {})
    tk.get_action('package_patch')(
        {'ignore_auth': True, 'user': site_user['name']},
        {'id': package_dict['id'], 'extras': new_extras},
    )

    if status == 'error':
        _create_failure_activity(package_dict, error)

    return {'status': status, 'error': error, 'next_sync': next_sync}


def _create_failure_activity(package_dict, error):
    """ Emit a CKAN activity stream entry recording a sync failure.

    Successes are not recorded here: CKAN already emits a 'changed package'
    activity for every successful resource_patch. Failures, in contrast, do
    not produce any activity by default — this is where they become visible.

    The activity is attributed to the dataset's creator (not the site user)
    so it shows up in the standard activity stream — CKAN filters out
    site-user activities from public streams by default.
    """
    if not plugin_loaded("activity"):
        return
    if not tk.config.get('ckan.activity_streams_enabled', True):
        return
    try:
        # Attribute to the dataset creator so the activity isn't hidden.
        # Fall back to site_user if creator is missing for any reason.
        user_id = package_dict.get('creator_user_id')
        if not user_id:
            user_id = tk.get_action('get_site_user')({'ignore_auth': True}, {})['name']

        from ckan.lib.plugins import get_permission_labels
        pkg_obj = model.Package.get(package_dict['id'])
        permission_labels = get_permission_labels().get_dataset_labels(pkg_obj) if pkg_obj else None

        tk.get_action('activity_create')(
            {'ignore_auth': True, 'user': user_id},
            {
                'user_id': user_id,
                'object_id': package_dict['id'],
                'activity_type': ACTIVITY_TYPE_SYNC_FAILED,
                'data': {
                    'package': {
                        'id': package_dict['id'],
                        'name': package_dict.get('name'),
                        'title': package_dict.get('title'),
                    },
                    'error': (error or '')[:500],
                    'chart_id': get_extra(package_dict, EXTRA_CHART_ID),
                },
                'permission_labels': permission_labels,
            },
        )
    except Exception:
        log.exception(
            f"Failed to record sync-failed activity for package {package_dict.get('id')}"
        )


def find_due_package_ids(now=None):
    """ Return IDs of active packages whose next sync time has arrived.

    Pre-conditions enforced via PackageExtra rows:
    - superset_chart_id present
    - superset_sync_enabled == 'true'
    - superset_next_sync <= now (ISO-8601 lexicographic comparison is correct)
    """
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    PE = model.PackageExtra

    chart_pkgs = model.Session.query(PE.package_id).filter(
        PE.key == EXTRA_CHART_ID, PE.state == 'active'
    )
    enabled_pkgs = model.Session.query(PE.package_id).filter(
        PE.key == EXTRA_ENABLED, PE.value == 'true', PE.state == 'active'
    )
    due_pkgs = model.Session.query(PE.package_id).filter(
        PE.key == EXTRA_NEXT_SYNC,
        PE.value <= now_iso,
        PE.state == 'active',
    )

    rows = model.Session.query(model.Package.id).filter(
        model.Package.id.in_(chart_pkgs.subquery()),
        model.Package.id.in_(enabled_pkgs.subquery()),
        model.Package.id.in_(due_pkgs.subquery()),
        model.Package.state == 'active',
    ).all()

    return [r[0] for r in rows]
