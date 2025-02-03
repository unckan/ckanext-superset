from types import SimpleNamespace
import pytest
from ckan.lib.helpers import url_for
from ckan.tests import factories
from io import BytesIO
from werkzeug.datastructures import FileStorage
from ckan.plugins import toolkit


@pytest.fixture
def setup_data():
    """Fixture para crear datos de prueba"""
    obj = SimpleNamespace()
    obj.sysadmin = factories.SysadminWithToken()
    obj.user_regular = factories.UserWithToken()
    obj.user_member_admin = factories.UserWithToken()
    obj.organization = factories.Organization()
    return obj


@pytest.mark.usefixtures('clean_db', 'clean_index', 'superset_migrate')
class TestSupersetViews:
    """Tests para las vistas de Superset"""

    def test_index_sysadmin_can_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede acceder a la vista de Superset"""

        auth_headers = {"Authorization": setup_data.sysadmin['token']}
        user_env = {"REMOTE_USER": setup_data.sysadmin['name']}
        url = url_for('superset_blueprint.index')

        # Obtener los datos del usuario a través de user_show
        try:
            user_data = toolkit.get_action('user_show')({}, {'id': setup_data.sysadmin['name']})
            print(f"🔍 Usuario detectado antes de la solicitud: {user_data}")
        except Exception as e:
            print(f"❌ Error al obtener datos del usuario en la prueba: {e}")
            user_data = None

        assert user_data, "No se encontró el usuario en CKAN"
        assert user_data.get('sysadmin', False), "El usuario no tiene permisos de sysadmin"

        response = app_httpx_mocked.get(url, headers=auth_headers, extra_environ=user_env)

        assert response.status_code == 200, f"Esperado 200, pero recibió {response.status_code}"
        assert 'Superset charts' in response.body, "No se encontró el texto esperado en la respuesta"

    def test_index_non_sysadmin_cannot_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede acceder a la vista de Superset"""
        auth = {"Authorization": setup_data.user_regular['token']}
        url = url_for('superset_blueprint.index')
        response = app_httpx_mocked.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_create_dataset_sysadmin_can_create(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede crear un dataset"""
        # Configuración de autenticación
        auth = {"Authorization": setup_data.sysadmin['token']}
        assert auth["Authorization"], "El token de autenticación está vacío o no válido"

        # Verificar acceso inicial al endpoint
        chart_id = 32
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app_httpx_mocked.get(url, extra_environ=auth)
        assert response.status_code == 200, "El endpoint no respondió correctamente"
        assert 'Create CKAN dataset from Superset dataset' in response.body, "El texto esperado no se encontró en la respuesta"

        # Simular el envío del formulario para crear un dataset
        data = {
            'ckan_dataset_title': 'Test Dataset',
            'ckan_dataset_notes': 'Some notes',
            'ckan_organization_id': setup_data.organization['id'],
            'ckan_dataset_private': False,
            'ckan_dataset_resource_name': FileStorage(
                stream=BytesIO(b"dummy data"),
                filename="test_resource.csv",
                content_type="text/csv"
            ),
        }
        # Realizar la solicitud POST
        response = app_httpx_mocked.post(url, extra_environ=auth, data=data)

        # Validar que la respuesta sea un código 200 (indica éxito sin redirección)
        assert response.status_code == 200, f"Se esperaba un 200, pero se recibió {response.status_code}"
        assert 'Dataset created successfully.' in response.body, "El mensaje de éxito no está presente en la respuesta."

        # Validar que el dataset creado se puede consultar en la lista de datasets
        dataset_url = url_for('dataset.read', id='test-dataset')
        dataset_response = app_httpx_mocked.get(dataset_url, extra_environ=auth)
        assert dataset_response.status_code == 200, "El dataset creado no está disponible."
        assert 'Test Dataset' in dataset_response.body, "El título del dataset no está presente en la respuesta."

    def test_create_dataset_non_sysadmin_cannot_create(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede crear un dataset"""
        auth = {"Authorization": setup_data.user_regular['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app_httpx_mocked.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_update_dataset_sysadmin_can_update(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede actualizar un dataset"""
        auth = {"Authorization": setup_data.sysadmin['token']}
        assert auth["Authorization"], "El token de autenticación está vacío o no válido"
        # Crear un dataset con un recurso asociado al chart_id
        # Verificar acceso inicial al endpoint
        chart_id = '32'
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app_httpx_mocked.get(url, extra_environ=auth)
        assert response.status_code == 200, "El endpoint no respondió correctamente"
        assert 'Create CKAN dataset from Superset dataset' in response.body, "El texto esperado no se encontró en la respuesta"

        # Simular el envío del formulario para crear un dataset
        data = {
            'ckan_dataset_title': 'Test Dataset',
            'ckan_dataset_notes': 'Some notes',
            'ckan_organization_id': setup_data.organization['id'],
            'ckan_dataset_private': False,
            'ckan_dataset_resource_name': FileStorage(
                stream=BytesIO(b"dummy data"),
                filename="test_resource.csv",
                content_type="text/csv"
            ),
        }
        # Realizar la solicitud POST
        response = app_httpx_mocked.post(url, extra_environ=auth, data=data)
        # Validar que la respuesta sea un código 200 (indica éxito sin redirección)
        assert response.status_code == 200, f"Se esperaba un 200, pero se recibió {response.status_code}"
        assert 'Dataset created successfully.' in response.body, "El mensaje de éxito no está presente en la respuesta."

        created_dataset = app_httpx_mocked.get(url_for('dataset.read', id='test-dataset'), extra_environ=auth)
        assert created_dataset.status_code == 200, "El dataset creado no está disponible."
        assert 'superset_chart_id' in created_dataset.body, "El dataset no está asociado al chart_id esperado."

        # Actualizar el dataset creado
        update_url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)
        update_response = app_httpx_mocked.post(update_url, extra_environ=auth)
        assert update_response.status_code == 200, f"Se esperaba un 200, pero se recibió {update_response.status_code}"
        assert 'updated successfully.' in update_response.body, "El mensaje de éxito no está presente en la respuesta."

    def test_update_dataset_non_sysadmin_cannot_update(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede actualizar un dataset"""
        auth = {"Authorization": setup_data.user_regular['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)
        response = app_httpx_mocked.post(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_list_databases_sysadmin_can_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede acceder a la lista de bases de datos"""
        auth = {"Authorization": setup_data.sysadmin['token']}
        url = url_for('superset_blueprint.list_databases')
        response = app_httpx_mocked.get(url, extra_environ=auth)
        assert response.status_code == 200
        assert 'databases' in response.body

    def test_list_databases_non_sysadmin_cannot_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede acceder a la lista de bases de datos"""
        auth = {"Authorization": setup_data.user_regular['token']}
        url = url_for('superset_blueprint.list_databases')
        response = app_httpx_mocked.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403

    def test_member_admin_cant_see(self, app, setup_data):
        """Test para verificar que un usuario miembro de una organización no puede acceder a la vista de Superset"""
        auth = {"Authorization": setup_data.user_member_admin['token']}
        url = url_for('superset_blueprint.index')
        response = app.get(url, headers=auth)
        assert response.status_code == 403
        assert 'Superset' not in response.body

    def test_sysadmin_can_see(self, app, setup_data):
        """Test para verificar que un sysadmin puede ver la vista de Superset"""
        auth = {"Authorization": setup_data.sysadmin['token']}
        url = url_for('admin.index')
        response = app.get(url, headers=auth)
        assert response.status_code == 200
        assert 'Superset' in response.body

    def test_member_admin_cant_see_superset(self, app, setup_data):
        """Test para verificar que un usuario miembro de una organización no puede ver la vista de Superset"""
        auth = {"Authorization": setup_data.user_member_admin['token']}
        url = url_for('admin.index')
        response = app.get(url, headers=auth)
        assert response.status_code == 403
        assert 'Superset' not in response.body
