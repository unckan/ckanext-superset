import httpx
import pytest

from ckanext.superset.tests.helpers import mock_transport


@pytest.fixture
def superset_migrate(migrate_db_for):
    # Migrar la base de datos de Superset
    # migrate_db_for('superset')
    pass


@pytest.fixture
def app_httpx_mocked(app, monkeypatch):
    """
    Devuelve una instancia de `app` con httpx configurado para usar un MockTransport.

    Este fixture permite interceptar las solicitudes httpx realizadas por CKAN
    durante las pruebas.
    """

    # Reemplaza el cliente httpx para que use el transporte de mock
    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: mock_client)

    # Devuelve la aplicación con el mock aplicado
    return app
