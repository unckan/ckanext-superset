import logging
from ckan.plugins import toolkit
from ckanext.superset.exceptions import SupersetRequestException


log = logging.getLogger(__name__)


class SupersetChart:
    """ An Apache Superset chart """

    def __init__(self, superset_instance=None):
        self.id = None
        self.data = {}
        self.superset_instance = superset_instance
        self._ckan_dataset = None

    def load(self, json_data):
        """ Load the dataset from a JSON object
        See /ckanext/superset/data/samples/chart.json
        """
        self.data = json_data
        self.id = json_data.get("id")

    def get_from_superset(self, chart_id):
        """ Get the dataset from Apache Superset """
        data = self.superset_instance.get(f"chart/{chart_id}")
        self.id = data.get("id")
        chart = data.pop("result", {})
        self.load(chart)

    def __getitem__(self, key):
        return self.data.get(key)

    @property
    def ckan_dataset(self):
        """ Returns the CKAN dataset create from this Superset dataset """
        if self._ckan_dataset:
            return self._ckan_dataset
        # Search a CKAN package with the extra superset_chart_id: self.id
        ctx = {"ignore_auth": True}
        search = {
            'fq': f'superset_chart_id:{self.id}',
            'include_private': True,
            'include_drafts': True,
        }
        pkgs = toolkit.get_action("package_search")(ctx, data_dict=search)
        if pkgs.get("count") > 0:
            self._ckan_dataset = pkgs.get("results")[0]
            return self._ckan_dataset
        return None

    def get_chart_data(self):
        """ Get the dataset data """
        return self.superset_instance.get(f"chart/{self.id}/data/")

    def get_chart_file(self, format_):
        """ Download a file from the dataset """
        log.debug(f"Downloading chart {self.id} as {format_}")
        format_ = format_.lower()
        url = f'chart/{self.id}/data/?format={format_}'
        response = self.superset_instance.get(url, format_=format_)
        log.info(f'RESPONSE: {url} :: {type(response)}')
        csv_data = response
        return csv_data

    def get_chart_csv(self):
        """ Get the dataset as CSV """
        return self.get_chart_file("csv")

    def get_thumbnail(self):
        """
        The api give us the field thumbnail_url with values like: /api/v1/chart/32/thumbnail/ce90a87d38fa6a2d8fa20232c1cba6f3/
        This method returns the full URL for the thumbnail.
        Considering we can be behind a proxy, we can't simply use the URL.
        """
        url = self.data.get("thumbnail_url")
        if not url:
            return None
        cleaned_url = url.replace("/api/v1/", "")
        try:
            image = self.superset_instance.get(cleaned_url, format_="image")
        except SupersetRequestException:
            return None

        return image
