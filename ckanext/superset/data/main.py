"""
Connect to the superset API (through a proxy server if required)
"""
import logging
import urllib.parse
import httpx
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

        self.datasets_response = None
        self.datasets = []  # {ID: data}

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

    def load_databases(self, force=False):
        if hasattr(self, 'databases') and self.databases and not force:
            return

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

    def prepare_connection(self):
        """ Define the client and login if required """
        log.info(f"Connecting to {self.superset_url}")
        if self.proxy_url:
            log.info(f"Using proxy {self.proxy_url}:{self.proxy_port}")
            self.client = httpx.Client(proxies=self.proxies, http2=False)
        else:
            self.client = httpx.Client()

        # If we have a user, then we need to login
        if self.superset_user:
            # prepare a user session
            # For some reason we need the API token AND the session cookie
            log.info(f"Logging Superset in as {self.superset_user}")
            # Get an access token for the API (works for data but not for CSV)
            login_url = f"{self.superset_url}/api/v1/security/login"
            login_response = self.client.post(login_url, json=self.login_payload)
            data = login_response.json()
            self.access_token = data["access_token"]

            # Get a session for the user (works for CSV)
            # POST to /login/ form with the username and password
            login_url = f"{self.superset_url}/login/"
            # Get the CSRF token from the login page
            # <input id="csrf_token" name="csrf_token" type="hidden" value="IjI1----">
            login_response = self.client.get(login_url)
            login_response.raise_for_status()
            csrf_token = login_response.text.split('csrf_token" type="hidden" value="')[1].split('"')[0]
            data = {
                "username": self.superset_user,
                "password": self.superset_pass,
                "csrf_token": csrf_token
            }
            login_response = self.client.post(login_url, data=data)
            # Get expect a 302 redirect to /
            if login_response.status_code != 302:
                login_response.raise_for_status()
            # Save cookies from the login response
            self.client.cookies.update(login_response.cookies)

        return self.client

    def get(self, endpoint, timeout=30, format_='json'):
        """ Get data from the Superset API """
        if not self.client:
            self.prepare_connection()

        headers = self.get_headers(format_=format_)

        url = f'{self.superset_url}/api/v1/{endpoint}'
        api_response = self.client.get(url, headers=headers, timeout=timeout)
        try:
            api_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error = (
                f"Error getting {url}\n\tStatus: {api_response.status_code}\n\t"
                f"ERR: {e}\n\t"
                f"Response: {api_response.text}\n\t"
            )
            private_error = f"{error}\n\t Headers: {headers}"
            log.error(private_error)
            raise SupersetRequestException(error)

        if format_ == 'csv':
            return api_response.content
        elif format_ == 'json':
            return api_response.json()

    def get_headers(self, format_='json'):
        """ Get the headers for the httpx client """
        if format_ == 'json':
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
        elif format_ == 'csv':
            headers = {"Content-Type": "text/csv", "Accept": "text/csv", "Accept-Encoding": "gzip, deflate, br, zstd"}

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    @property
    def proxies(self):
        """ The httpx proxies dictionary """
        return {
            "http://": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_url}:{self.proxy_port}",
            "https://": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_url}:{self.proxy_port}",
        }

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
        try:
            response = self.client.get(test_url)
            response.raise_for_status()
            log.debug(f'Proxy test successful: {response.json()}')
            return True
        except Exception as e:
            log.error(f'Proxy test failed: {e}')
            return False
