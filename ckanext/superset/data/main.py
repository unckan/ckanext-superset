"""
Connect to the superset API (through a proxy server if required)
"""
import logging
import urllib.parse
import httpx
from ckanext.superset.data.dataset import SupersetDataset


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
            ds = SupersetDataset()
            ds.load(dataset)
            self.datasets.append(ds)

    def prepare_connection(self):
        """ Define the client and login if required """

        if self.proxy_url:
            self.client = httpx.Client(proxies=self.proxies, http2=False)
        else:
            self.client = httpx.Client()

        # If we have a user, then we need to login
        if self.superset_user:
            login_url = f"{self.superset_url}/api/v1/security/login"
            log.info(f"Login response: {login_url} {self.login_payload}")
            login_response = self.client.post(login_url, json=self.login_payload)
            login_response.raise_for_status()
            data = login_response.json()
            self.access_token = data["access_token"]

        return self.client

    def get(self, endpoint):
        """ Get data from the Superset API """
        if not self.client:
            self.prepare_connection()

        headers = self.get_headers()

        url = f'{self.superset_url}/api/v1/{endpoint}'
        api_response = self.client.get(url, headers=headers)
        try:
            api_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            log.error(f"Error getting {url}: {e}")
            log.error(f"Response: {api_response.text}")
            return {
                "error": f"Error getting {url}: {e}",
                "response": api_response.text,
            }

        data = api_response.json()
        return data

    def get_headers(self):
        """ Get the headers for the httpx client """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
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
