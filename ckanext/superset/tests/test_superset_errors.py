"""
A failing Superset must not end in a raw 500: CKAN answers with a gateway
status (502 Bad Gateway / 504 Gateway Timeout) and a readable message.
"""
import httpx
import pytest
from ckan.lib.helpers import url_for
from ckan.tests import factories

from ckanext.superset.config import get_config
from ckanext.superset.data.main import SupersetCKAN
from ckanext.superset.exceptions import SupersetRequestException
from ckanext.superset.tests.helpers import mock_transport


def _timeout_on_login_page(request):
    """ The API login works, but the /login/ page (session login) times out """
    if request.url.path == '/login/':
        raise httpx.ReadTimeout('The read operation timed out', request=request)
    return mock_transport(request)


def _connect_error(request):
    raise httpx.ConnectError('Connection refused', request=request)


def _login_without_redirect(request):
    """ The session login answers 200 instead of the expected 302 """
    if request.method == 'POST' and request.url.path == '/login/':
        return httpx.Response(200, content='Login form again')
    return mock_transport(request)


def _mock_httpx(monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, 'Client', lambda *args, **kwargs: client)


@pytest.fixture
def sysadmin_headers():
    sysadmin = factories.SysadminWithToken()
    return {'Authorization': sysadmin['token']}


@pytest.mark.usefixtures('with_plugins')
class TestSupersetRequestStatus:

    def test_timeout_is_504(self, monkeypatch):
        _mock_httpx(monkeypatch, _timeout_on_login_page)
        with pytest.raises(SupersetRequestException) as e:
            SupersetCKAN(**get_config()).prepare_connection()
        assert e.value.status_code == 504

    def test_connect_error_is_502(self, monkeypatch):
        _mock_httpx(monkeypatch, _connect_error)
        with pytest.raises(SupersetRequestException) as e:
            SupersetCKAN(**get_config()).prepare_connection()
        assert e.value.status_code == 502

    def test_unexpected_login_status_is_502(self, monkeypatch):
        _mock_httpx(monkeypatch, _login_without_redirect)
        with pytest.raises(SupersetRequestException) as e:
            SupersetCKAN(**get_config()).prepare_connection()
        assert e.value.status_code == 502


@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
class TestSupersetErrorPages:

    @pytest.mark.parametrize('endpoint', [
        'superset_blueprint.index',
        'superset_blueprint.list_databases',
        'superset_blueprint.list_datasets',
    ])
    def test_timeout_renders_504_page(self, app, monkeypatch, sysadmin_headers, endpoint):
        _mock_httpx(monkeypatch, _timeout_on_login_page)
        response = app.get(url_for(endpoint), headers=sysadmin_headers)
        assert response.status_code == 504
        assert 'Apache Superset is taking too long to respond' in response.body

    def test_connect_error_renders_502_page(self, app, monkeypatch, sysadmin_headers):
        _mock_httpx(monkeypatch, _connect_error)
        url = url_for('superset_blueprint.create_dataset', chart_id='32')
        response = app.get(url, headers=sysadmin_headers)
        assert response.status_code == 502
        assert 'Apache Superset is not available right now' in response.body

    def test_chart_image_error_is_plain_text(self, app, monkeypatch, sysadmin_headers):
        _mock_httpx(monkeypatch, _connect_error)
        url = url_for('superset_images.chart_image', chart_id=32)
        response = app.get(url, headers=sysadmin_headers)
        assert response.status_code == 502
        assert response.headers['Content-Type'].startswith('text/plain')
        assert 'Apache Superset is not available right now' in response.body
