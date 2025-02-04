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

    def test_superset_settings(self):
        """Verifica si la configuración de Superset se está cargando correctamente"""
        config_keys = [
            "ckanext.superset.instance.url",
            "ckanext.superset.instance.user",
            "ckanext.superset.instance.pass",
            "ckanext.superset.instance.provider",
            "ckanext.superset.instance.refresh",
        ]

        for key in config_keys:
            value = toolkit.config.get(key, "NO ENCONTRADO")
            print(f"{key}: {value}")

        assert toolkit.config.get("ckanext.superset.instance.url") is not None, "URL de Superset no encontrada"
        assert toolkit.config.get("ckanext.superset.instance.user") is not None, "Usuario de Superset no encontrado"
        assert toolkit.config.get("ckanext.superset.instance.pass") is not None, "Contraseña de Superset no encontrada"
        assert toolkit.config.get("ckanext.superset.instance.provider") is not None, "Proveedor de Superset no encontrado"
        assert toolkit.config.get("ckanext.superset.instance.refresh") is not None, "Configuración de actualización de Superset no encontrada"

    def test_index_sysadmin_can_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede acceder a la vista de Superset"""

        auth_headers = {
            "Authorization": setup_data.sysadmin["token"],
            "X-CSRF-Token": "test_csrf_token"
        }
        url = url_for('superset_blueprint.index')

        print(f"🔹 URL de solicitud: {url}")
        print(f"🔹 Headers enviados: {auth_headers}")

        # Obtener los datos del usuario a través de user_show
        try:
            user_data = toolkit.get_action('user_show')({}, {'id': setup_data.sysadmin['name']})
            print(f"🔍 Usuario detectado antes de la solicitud: {user_data}")
        except Exception as e:
            print(f"❌ Error al obtener datos del usuario en la prueba: {e}")
            user_data = None

        assert user_data, "No se encontró el usuario en CKAN"
        assert user_data.get('sysadmin', False), "El usuario no tiene permisos de sysadmin"

        response = app_httpx_mocked.get(url, headers=auth_headers)

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
        auth_headers = {
            "Authorization": setup_data.sysadmin["token"],
            "X-CSRF-Token": "test_csrf_token"
        }
        chart_id = 32
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)

        print(f"🔹 URL de solicitud: {url}")
        print(f"🔹 Headers enviados: {auth_headers}")

        response = app_httpx_mocked.get(url, headers=auth_headers)
        assert response.status_code == 200, "El endpoint no respondió correctamente"
        assert 'Create CKAN dataset from Superset dataset' in response.text, "No se encontró el texto esperado"

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
        response = app_httpx_mocked.post(url, headers=auth_headers, data=data)

        # Validar que la respuesta sea un código 200 (indica éxito sin redirección)
        assert response.status_code == 200, f"Se esperaba un 200, pero se recibió {response.status_code}"
        assert 'Dataset created successfully and added to the selected groups.' in response.text, "El mensaje de éxito no está presente"


        # Validar que el dataset creado se puede consultar en la lista de datasets
        dataset_url = url_for('dataset.read', id='test-dataset')
        dataset_response = app_httpx_mocked.get(dataset_url, headers=auth_headers)
        assert dataset_response.status_code == 200, "El dataset creado no está disponible."
        assert 'Test Dataset' in dataset_response.body, "El título del dataset no está presente en la respuesta."

    def test_create_dataset_non_sysadmin_cannot_create(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede crear un dataset"""
        auth = {"Authorization": setup_data.user_regular['token']}
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        response = app_httpx_mocked.get(url, extra_environ=auth, expect_errors=True)
        assert response.status_code == 403
        assert 'Forbidden' in response.text

    def test_update_dataset_sysadmin_can_update(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede actualizar un dataset"""
        auth_headers = {
            "Authorization": setup_data.sysadmin["token"],
            "X-CSRF-Token": "test_csrf_token"
        }
        chart_id = '32'

        # **Crear primero el dataset antes de actualizarlo**
        create_url = url_for('superset_blueprint.create_dataset', chart_id=chart_id)
        create_data = {
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
        create_response = app_httpx_mocked.post(create_url, headers=auth_headers, data=create_data)
        assert create_response.status_code == 200, f"Error al crear dataset: {create_response.status_code}"
        assert 'Dataset created successfully' in create_response.text, "El mensaje de éxito no está presente en la respuesta."

        # **Confirmar que el dataset ahora existe**
        dataset_url = url_for('dataset.read', id='test-dataset')
        dataset_response = app_httpx_mocked.get(dataset_url, headers=auth_headers)
        assert dataset_response.status_code == 200, "El dataset creado no está disponible."

        # **Ahora proceder con la actualización**
        update_url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)
        update_response = app_httpx_mocked.post(update_url, headers=auth_headers)

        # **Validar la actualización**
        assert update_response.status_code == 200, f"Se esperaba un 200, pero se recibió {update_response.status_code}"
        assert 'updated successfully' in update_response.text, "El mensaje de éxito no está presente en la respuesta."

    def test_update_dataset_non_sysadmin_cannot_update(self, app_httpx_mocked, setup_data):
        """Test para verificar que un usuario no sysadmin no puede actualizar un dataset"""
        auth_headers = {
            "Authorization": setup_data.user_regular["token"],
            "X-CSRF-Token": "test_csrf_token"
        }
        chart_id = 'test_chart'
        url = url_for('superset_blueprint.update_dataset', chart_id=chart_id)

        response = app_httpx_mocked.post(url, headers=auth_headers, expect_errors=True)

        # Verificar código de estado
        assert response.status_code == 403, f"Se esperaba 403 Forbidden, pero se recibió {response.status_code}"
        
        # Verificar el mensaje correcto en la respuesta
        expected_message = "Sysadmin user required"
        assert expected_message in response.text, f"No se encontró el mensaje esperado en la respuesta. Respuesta recibida: {response.text}"


    def test_list_databases_sysadmin_can_access(self, app_httpx_mocked, setup_data):
        """Test para verificar que un sysadmin puede acceder a la lista de bases de datos"""
        auth_headers = {
            "Authorization": setup_data.sysadmin["token"],
            "X-CSRF-Token": "test_csrf_token"
        }
        url = url_for('superset_blueprint.list_databases')

        print(f"🔹 URL de solicitud: {url}")
        print(f"🔹 Headers enviados: {auth_headers}")

        response = app_httpx_mocked.get(url, headers=auth_headers)
        assert response.status_code == 200, f"Se esperaba un 200, pero se recibió {response.status_code}"
        assert 'databases' in response.text, "No se encontró la clave 'databases' en la respuesta"

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
