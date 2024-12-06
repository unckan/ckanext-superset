from types import SimpleNamespace
import pytest
from ckan.lib.helpers import url_for
from ckan.tests import factories


@pytest.fixture
def setup_data():
    """Fixture para crear datos de prueba"""
    obj = SimpleNamespace()
    obj.sysadmin = factories.SysadminWithToken()
    obj.user_regular = factories.UserWithToken()
    obj.organization = factories.Organization()
    return obj


@pytest.mark.usefixtures('clean_db', 'clean_index', 'superset_migrate')
class TestSupersetViews:
    """Tests para las vistas de Superset"""

    def test_index_sysadmin_can_access(self, app, setup_data):
        auth = {"Authorization": setup_data.sysadmin['token']}
        url = url_for('superset_blueprint.index')
        response = app.get(url, extra_environ=auth)
        assert response.status_code == 200
        assert 'charts_count' in response.body

    def test_index_non_sysadmin_cannot_access(self, app, setup_data):
        auth = {"Authorization": setup_data.user_regular['token']}
        url = url_for('superset_blueprint.index')
        response = app.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_create_dataset_sysadmin_can_create(self, app, setup_data):
        auth = {"Authorization": setup_data.sysadmin['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app.get(url, extra_environ=auth)
        assert response.status_code == 200
        assert 'Create Dataset' in response.body

        # Simular el envío del formulario
        data = {
            'ckan_dataset_title': 'Test Dataset',
            'ckan_dataset_notes': 'Some notes',
            'ckan_organization_id': setup_data.organization['id'],
            'ckan_dataset_private': True,
            'ckan_dataset_resource_name': 'Test Resource',
        }
        response = app.post(url, extra_environ=auth, data=data)
        assert response.status_code == 302  # Redirección al dataset creado

    def test_create_dataset_non_sysadmin_cannot_create(self, app, setup_data):
        auth = {"Authorization": setup_data.user_regular['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_update_dataset_sysadmin_can_update(self, app, setup_data):
        auth = {"Authorization": setup_data.sysadmin['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)

        # Simular el envío del formulario
        data = {'ckan_dataset_resource_name': 'Updated Resource'}
        response = app.post(url, extra_environ=auth, data=data)
        assert response.status_code == 302  # Redirección al dataset actualizado

    def test_update_dataset_non_sysadmin_cannot_update(self, app, setup_data):
        auth = {"Authorization": setup_data.user_regular['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)
        response = app.post(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_list_databases_sysadmin_can_access(self, app, setup_data):
        auth = {"Authorization": setup_data.sysadmin['token']}
        url = url_for('superset_blueprint.list_databases')
        response = app.get(url, extra_environ=auth)
        assert response.status_code == 200
        assert 'databases' in response.body

    def test_list_databases_non_sysadmin_cannot_access(self, app, setup_data):
        auth = {"Authorization": setup_data.user_regular['token']}
        url = url_for('superset_blueprint.list_databases')
        response = app.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403
