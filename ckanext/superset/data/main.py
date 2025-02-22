"""
Connect to the superset API (through a proxy server if required)
"""
import json
import logging
import urllib.parse
import httpx
import traceback
from ckanext.superset.data.chart import SupersetChart
from httpx import Proxy
from ckanext.superset.data.dataset import SupersetDataset
from ckanext.superset.exceptions import SupersetRequestException


log = logging.getLogger(__name__)


class SupersetCKAN:
    """ A class to connect to a Superset instance """

    def __init__(
        self, superset_url,
        superset_user=None, superset_pass=None,
        proxy_url=None, proxy_port=3128, proxy_user=None, proxy_pass=None,
        superset_provider="db", superset_refresh="true"
    ):
        self.superset_url = superset_url
        self.superset_user = superset_user
        self.superset_pass = superset_pass
        self.superset_provider = superset_provider
        self.superset_refresh = superset_refresh
        self.proxy_url = proxy_url
        self.proxy_port = proxy_port
        if proxy_user:
            # Encode the proxy user and password
            self.proxy_user = urllib.parse.quote(proxy_user)
        else:
            self.proxy_user = None
        if proxy_pass:
            self.proxy_pass = urllib.parse.quote(proxy_pass)
        else:
            self.proxy_pass = None
        # Preserve a session for the client (httpx.Client)
        self.client = None
        # In case we need to login
        self.access_token = None

        self.charts_response = None
        self.charts = []  # {ID: data}

        self.datasets_response = None
        self.datasets = []  # {ID: data}

        self.databases_response = None
        self.databases = []  # {ID: data}

    def load_datasets(self, force=False):
        """ Get and load all datasets """
        if self.datasets and not force:
            return

        # Ver ckanext/superset/data/samples/datasets.json
        self.datasets_response = self.get("dataset/")
        datasets = self.datasets_response.get("result", {})
        for dataset in datasets:
            ds = SupersetDataset(superset_instance=self)
            ds.load(dataset)
            self.datasets.append(ds)
        return self.datasets

    def load_charts(self, force=False):
        """ Get and load all datasets
            Ver ckanext/superset/data/samples/chaerts.json
        """
        if self.charts and not force:
            return

        q_data = {"page_size": 50, "page": 0}
        while True:
            params = {'q': json.dumps(q_data)}
            self.charts_response = self.get("chart/", params=params)

            if not self.charts_response or not self.charts_response.get("result", {}):
                break

            charts = self.charts_response.get("result", {})
            for chart in charts:
                ds = SupersetChart(superset_instance=self)
                ds.load(chart)
                self.charts.append(ds)
            q_data["page"] += 1
            if q_data["page"] > 20:
                log.error("Too many pages of charts")
                break
        return self.charts

    def load_databases(self, force=False):
        if self.databases and not force:
            return self.databases

        self.databases_response = self.get("database/")
        self.databases = sorted(
            self.databases_response.get("result", []),
            key=lambda x: x["id"]
        )

        return self.databases

    def get_dataset(self, dataset_id):
        """ Get a dataset by ID """
        for dataset in self.datasets:
            if dataset.id == dataset_id:
                return dataset
        # Get from the API
        dataset = SupersetDataset(superset_instance=self)
        dataset.get_from_superset(dataset_id)
        self.datasets.append(dataset)
        return dataset

    def get_chart(self, chart_id):
        """ Get a chart by ID """
        for chart in self.charts:
            if chart.id == chart_id:
                return chart
        # Get from the API
        chart = SupersetChart(superset_instance=self)
        chart.get_from_superset(chart_id)
        self.charts.append(chart)
        return chart

    def get_databases(self):
        """ Get a list_database """
        # Get from the API
        self.load_databases(self)
        return self.databases

    def prepare_connection(self):
        """ Define the client and login if required """
        log.info(f"Connecting to {self.superset_url}")
        if self.proxy_url:
            log.info(f"Using proxy {self.proxy_url}:{self.proxy_port}")
            proxy = Proxy(self.proxy_full_url)
            self.client = httpx.Client(transport=httpx.HTTPTransport(proxy=proxy))
        else:
            self.client = httpx.Client()

        # If we have a user, then we need to login
        if self.superset_user:
            # prepare a user session
            # For some reason we need the API token AND the session cookie
            log.info(f"Logging Superset in as {self.superset_user}")
            # Get an access token for the API (works for data but not for CSV)
            login_url = f"{self.superset_url}/api/v1/security/login"
            login_response, error = self.request("POST", login_url, json=self.login_payload)
            if not login_response:
                raise SupersetRequestException(error)
            data = login_response.json()
            if "access_token" not in data:
                error = f"Error getting access token from Superset: {data}"
                log.critical(error)
                raise SupersetRequestException(error)

            self.access_token = data["access_token"]

            # Get a session for the user (works for CSV)
            # POST to /login/ form with the username and password
            login_url = f"{self.superset_url}/login/"
            # Get the CSRF token from the login page
            # <input id="csrf_token" name="csrf_token" type="hidden" value="IjI1----">
            login_response = self.request("GET", login_url)
            if not login_response:
                raise SupersetRequestException(error)

            csrf_token = login_response.text.split('csrf_token" type="hidden" value="')[1].split('"')[0]
            data = {
                "username": self.superset_user,
                "password": self.superset_pass,
                "csrf_token": csrf_token
            }
            login_response = self.request("POST", login_url, data=data)
            if not login_response:
                raise SupersetRequestException(error)
            # Get expect a 302 redirect to /
            if login_response.status_code != 302:
                error = f"Unexpected status code: {login_response.status_code} from Superset login"
                log.critical(error)
                login_response.raise_for_status()
            # Save cookies from the login response
            self.client.cookies.update(login_response.cookies)

        return self.client

    def get(self, endpoint, timeout=30, format_='json', params=None):
        """ Get data from the Superset API
            parameter data is user as GET parameters. It must be a dictionary
        """
        if not self.client:
            self.prepare_connection()

        headers = self.get_headers(format_=format_)

        url = f'{self.superset_url}/api/v1/{endpoint}'
        log.info(f"Superset GET {url} :: {params}")
        api_response, error = self.safe_request("GET", url, headers=headers, params=params, timeout=timeout)
        if not api_response:
            raise SupersetRequestException(error)

        if format_ == 'csv':
            return api_response.content
        elif format_ == 'json':
            return api_response.json()
        elif format_ == 'image':  # Thumbnail images
            return api_response.content

    def request(self, method, url, **kwargs):
        """ Perform an HTTP request safely with detailed error handling
            Returns the response and None if successful, otherwise None and an error message
        """
        try:
            if method == "GET":
                response = self.client.get(url, **kwargs)
            elif method == "POST":
                response = self.client.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            return response, None
        except httpx.HTTPStatusError as e:
            error = f"HTTP error {e.response.status_code} while accessing Superset."
            self.handle_error(url, e, error)
        except httpx.ConnectError as e:
            error = "Failed to connect to Superset."
            self.handle_error(url, e, error)
        except httpx.TimeoutException as e:
            error = "Request to Superset timed out."
            self.handle_error(url, e, error)
        except Exception as e:
            error = "An unexpected error occurred while communicating with Superset."
            self.handle_error(url, e, error)

        return None, error

    def handle_error(self, url, exception, public_message):
        """ Log detailed error information and raise an exception """
        # error_type is the error class name
        error_type = exception.__class__.__name__
        error_details = (
            f"Superset request error: {error_type} occurred during request to {url}.\n"
            f"Exception: {exception}\n"
            f"Traceback: {traceback.format_exc(limit=10)}"
        )
        log.critical(error_details)  # Log interno para push-errors
        raise SupersetRequestException(public_message) from exception

    def get_headers(self, format_='json'):
        """ Get the headers for the httpx client """
        if format_ == 'json':
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
        elif format_ == 'csv':
            headers = {"Content-Type": "text/csv", "Accept": "text/csv", "Accept-Encoding": "gzip, deflate, br, zstd"}
        elif format_ == 'image':
            headers = {"Content-Type": "image/png", "Accept": "image/png"}

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    @property
    def proxy_full_url(self):
        """ The httpx proxy full URL with user and password """
        return f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_url}:{self.proxy_port}"

    @property
    def login_payload(self):
        return {
            "username": self.superset_user,
            "password": self.superset_pass,
            "provider": self.superset_provider,
            "refresh": self.superset_refresh,
        }

    def test_proxy(self, test_url="http://httpbin.org/ip"):
        """ Test the proxy connection """
        # Test proxy before going further (to superset)
        response, error = self.request("GET", test_url)
        if not response:
            return False
        log.debug(f'Proxy test successful: {response.json()}')
        return True
