"""
Tests for the periodic Superset sync module.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from ckan.lib.helpers import url_for
from ckan.plugins import toolkit
from ckan.tests import factories as ckan_factories

from ckanext.superset.data import sync as sync_module
from ckanext.superset.tests import factories


@pytest.fixture
def setup_data():
    obj = SimpleNamespace()
    obj.sysadmin = ckan_factories.SysadminWithToken()
    obj.user_regular = ckan_factories.UserWithToken()
    obj.organization = ckan_factories.Organization()
    return obj


class TestCalculateNextSync:

    def test_daily_adds_one_day(self):
        base = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
        assert sync_module.calculate_next_sync('daily', from_dt=base) == base + timedelta(days=1)

    def test_weekly_adds_seven_days(self):
        base = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
        assert sync_module.calculate_next_sync('weekly', from_dt=base) == base + timedelta(days=7)

    def test_monthly_adds_thirty_days(self):
        base = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
        assert sync_module.calculate_next_sync('monthly', from_dt=base) == base + timedelta(days=30)

    def test_none_returns_none(self):
        assert sync_module.calculate_next_sync('none') is None

    def test_unknown_returns_none(self):
        assert sync_module.calculate_next_sync('hourly') is None

    def test_missing_returns_none(self):
        assert sync_module.calculate_next_sync(None) is None


class TestMergeExtras:

    def test_adds_new_key(self):
        pkg = {'extras': []}
        result = sync_module.merge_extras(pkg, {'foo': 'bar'})
        assert result == [{'key': 'foo', 'value': 'bar'}]

    def test_overwrites_existing_key(self):
        pkg = {'extras': [{'key': 'foo', 'value': 'old'}]}
        result = sync_module.merge_extras(pkg, {'foo': 'new'})
        assert result == [{'key': 'foo', 'value': 'new'}]

    def test_none_value_removes_key(self):
        pkg = {'extras': [{'key': 'foo', 'value': 'old'}, {'key': 'keep', 'value': 'me'}]}
        result = sync_module.merge_extras(pkg, {'foo': None})
        assert result == [{'key': 'keep', 'value': 'me'}]

    def test_preserves_unrelated_keys(self):
        pkg = {'extras': [{'key': 'a', 'value': '1'}, {'key': 'b', 'value': '2'}]}
        result = sync_module.merge_extras(pkg, {'c': '3'})
        assert sorted(result, key=lambda e: e['key']) == [
            {'key': 'a', 'value': '1'},
            {'key': 'b', 'value': '2'},
            {'key': 'c', 'value': '3'},
        ]


@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
class TestSyncSettingsAndScheduler:

    def _ctx(self, setup_data):
        return {'user': setup_data.sysadmin['name']}

    def test_existing_dataset_has_no_sync_extras_by_default(self, setup_data):
        """ A freshly-linked dataset carries no sync extras. """
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        assert sync_module.get_extra(pkg, sync_module.EXTRA_FREQUENCY) is None
        assert sync_module.get_extra(pkg, sync_module.EXTRA_ENABLED) is None
        assert sync_module.get_extra(pkg, sync_module.EXTRA_NEXT_SYNC) is None

    def test_update_sync_settings_enables_and_schedules(self, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)

        sync_module.update_sync_settings(pkg['id'], 'daily', True, self._ctx(setup_data))

        refreshed = toolkit.get_action('package_show')({'ignore_auth': True}, {'id': pkg['id']})
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_FREQUENCY) == 'daily'
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_ENABLED) == 'true'
        next_sync = sync_module.get_extra(refreshed, sync_module.EXTRA_NEXT_SYNC)
        assert next_sync is not None
        datetime.fromisoformat(next_sync)

    def test_update_sync_settings_disable_clears_next_sync(self, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        ctx = self._ctx(setup_data)

        sync_module.update_sync_settings(pkg['id'], 'daily', True, ctx)
        sync_module.update_sync_settings(pkg['id'], 'daily', False, ctx)

        refreshed = toolkit.get_action('package_show')({'ignore_auth': True}, {'id': pkg['id']})
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_ENABLED) == 'false'
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_NEXT_SYNC) is None

    def test_update_sync_settings_invalid_frequency_raises(self, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        with pytest.raises(toolkit.ValidationError):
            sync_module.update_sync_settings(pkg['id'], 'hourly', True, self._ctx(setup_data))

    def test_find_due_excludes_unconfigured_packages(self, setup_data):
        factories.SupersetDataset(user=setup_data.sysadmin)
        assert sync_module.find_due_package_ids() == []

    def test_find_due_includes_packages_past_next_sync(self, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        sync_module.update_sync_settings(pkg['id'], 'daily', True, self._ctx(setup_data))

        future = datetime.now(timezone.utc) + timedelta(days=365)
        assert pkg['id'] in sync_module.find_due_package_ids(now=future)

    def test_find_due_excludes_disabled_packages(self, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        ctx = self._ctx(setup_data)
        sync_module.update_sync_settings(pkg['id'], 'daily', True, ctx)
        sync_module.update_sync_settings(pkg['id'], 'daily', False, ctx)

        future = datetime.now(timezone.utc) + timedelta(days=365)
        assert pkg['id'] not in sync_module.find_due_package_ids(now=future)

    def test_sync_dataset_records_success(self, app_httpx_mocked, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin, chart_id='32')
        factories.SupersetResource(package_id=pkg['id'], user=setup_data.sysadmin)
        sync_module.update_sync_settings(pkg['id'], 'daily', True, self._ctx(setup_data))

        result = sync_module.sync_dataset(pkg['id'])
        assert result['status'] == 'ok'

        refreshed = toolkit.get_action('package_show')({'ignore_auth': True}, {'id': pkg['id']})
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_LAST_STATUS) == 'ok'
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_LAST_SYNC) is not None
        assert sync_module.get_extra(refreshed, sync_module.EXTRA_NEXT_SYNC) is not None

    @pytest.mark.ckan_config('ckan.plugins', 'activity superset')
    def test_sync_failure_creates_activity(self, setup_data):
        """ A sync failure must surface in the dataset's CKAN activity stream. """
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)

        # Force a failure by calling the internal recorder directly.
        # (Easier than mocking SupersetCKAN; the contract under test is that
        # _record_result with status='error' emits an activity.)
        sync_module._record_result(pkg, status='error', error='Boom: chart unreachable')

        activities = toolkit.get_action('package_activity_list')(
            self._ctx(setup_data), {'id': pkg['id']},
        )
        sync_failures = [a for a in activities
                         if a['activity_type'] == sync_module.ACTIVITY_TYPE_SYNC_FAILED]
        assert len(sync_failures) == 1
        assert sync_failures[0]['data']['error'] == 'Boom: chart unreachable'
        assert sync_failures[0]['data']['package']['id'] == pkg['id']

    @pytest.mark.ckan_config('ckan.plugins', 'activity superset')
    def test_sync_success_does_not_create_failure_activity(self, app_httpx_mocked, setup_data):
        """ Successful syncs must not emit a 'superset sync failed' activity. """
        pkg = factories.SupersetDataset(user=setup_data.sysadmin, chart_id='32')
        factories.SupersetResource(package_id=pkg['id'], user=setup_data.sysadmin)
        sync_module.update_sync_settings(pkg['id'], 'daily', True, self._ctx(setup_data))

        sync_module.sync_dataset(pkg['id'])

        activities = toolkit.get_action('package_activity_list')(
            self._ctx(setup_data), {'id': pkg['id']},
        )
        sync_failures = [a for a in activities
                         if a['activity_type'] == sync_module.ACTIVITY_TYPE_SYNC_FAILED]
        assert sync_failures == []

    def test_sync_settings_view_requires_login(self, app_httpx_mocked, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        url = url_for('superset_blueprint.sync_settings', package_id=pkg['id'])
        response = app_httpx_mocked.get(url, expect_errors=True)
        assert response.status_code == 403

    def test_sync_settings_view_owner_can_access(self, app_httpx_mocked, setup_data):
        pkg = factories.SupersetDataset(user=setup_data.sysadmin)
        headers = {
            "Authorization": setup_data.sysadmin["token"],
            "X-CSRF-Token": "test_csrf_token",
        }
        url = url_for('superset_blueprint.sync_settings', package_id=pkg['id'])
        response = app_httpx_mocked.get(url, headers=headers)
        assert response.status_code == 200
        assert 'Periodic Apache Superset sync' in response.body
