"""
Superset test helpers
"""
import importlib
import json
from pathlib import Path
import httpx
from ckan.plugins.toolkit import config


def mock_transport(request: httpx.Request) -> httpx.Response:
    superset_test_url = config.get("ckanext.superset.instance.url")
    if not superset_test_url:
        return httpx.Response(404, json={"error": "Undefined Superset instance URL"})
    full_host = f'https://{request.url.host}'
    if not full_host == superset_test_url:
        return httpx.Response(404, json={"error": f"Unexpected host: {full_host} != {superset_test_url}"})

    method = request.method.lower()
    path = request.url.path
    query_params = request.url.query
    # drop query from URL
    paths = path.split("?")
    path = paths[0]
    # We will create a function for each request here
    clean_path = path.strip("/").replace("/", "__").replace("-", "_")
    fn = f'{method}_{clean_path}'
    # check if fn exist here in this module
    fno = getattr(importlib.import_module(__name__), fn, None)
    if fno is None:
        return httpx.Response(424, json={"error": f"Function {fn} not found in {__name__}"})

    # The function must return a httpx.Response object
    return fno(request, params=query_params)


def get_api__v1__chart(request: httpx.Request, params=None) -> httpx.Response:

    response = _get_from_samples('chart.json')
    if not response:
        return httpx.Response(404, json={"error": "Not found"})
    data = json.loads(response)
    return httpx.Response(200, json=data)


def post_api__v1__security__login(request: httpx.Request, params=None) -> httpx.Response:
    """ Mock the login endpoint """
    data = {
        'access_token': 'test_token',
    }
    return httpx.Response(200, json=data)


def get_login(request: httpx.Request, params=None) -> httpx.Response:
    """ This is an HTML response with the CSRF token """
    response = (
        "<html>"
        'csrf_token" type="hidden" value="test_csrf_token"'
        "</html>"
    )
    return httpx.Response(200, content=response)


def post_login(request: httpx.Request, params=None) -> httpx.Response:
    return httpx.Response(302, content="Redirect to /")


def _get_from_samples(path):
    here = Path(__file__).parent
    samples_folder = here / 'responses'

    json_file = samples_folder / f'{path}'
    if json_file.exists():
        return json_file.read_text()

    raise FileNotFoundError(f"File not found: {json_file}")


def get_api__v1__chart__32(request: httpx.Request, params=None) -> httpx.Response:
    """Mock del endpoint chart/{chart_id} cargando un JSON desde un archivo."""
    file_path = Path(__file__).parent / 'responses' / 'chart_32.json'
    if not file_path.exists():
        return httpx.Response(404, json={"error": "Mock file not found"})

    with open(file_path, 'r') as f:
        data = json.load(f)

    return httpx.Response(200, json=data)


def get_api__v1__chart__32__data(request: httpx.Request, params=None) -> httpx.Response:
    """Mock para el endpoint de descarga de datos CSV."""
    csv_content = "year,cantidad_mundos\n2021,50\n2022,70\n2023,90"
    headers = {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=test_chart.csv"
    }
    return httpx.Response(200, content=csv_content, headers=headers)


def get_api__v1__database(request: httpx.Request, params=None) -> httpx.Response:
    """Mock del endpoint de listado de bases de datos."""
    file_path = Path(__file__).parent / 'responses' / 'chart.json'

    if not file_path.exists():
        return httpx.Response(404, json={"error": "Mock file not found"})
    with open(file_path, 'r') as f:
        data = json.load(f)

    return httpx.Response(200, json=data)


def get_api__v1__chart__test_chart(request: httpx.Request, params=None) -> httpx.Response:
    """Mock para el endpoint chart/test_chart."""
    chart_data = {
        "id": "32",
        "name": "Test Chart",
        "description": "Mock chart data"
    }
    return httpx.Response(200, json=chart_data)
