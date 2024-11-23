import logging


log = logging.getLogger(__name__)


class SupersetDataset:
    """ An Apache Superset dataset """

    def __init__(self, superset_instance=None):
        self.id = None
        self.data = {}
        self.superset_instance = superset_instance

    def load(self, json_data):
        """ Load the dataset from a JSON object
        See /ckanext/superset/data/samples/dataset.json
        """
        self.data = json_data
        self.id = json_data.get("id")

    def get_from_superset(self, dataset_id):
        """ Get the dataset from Apache Superset """
        data = self.superset_instance.get(f"dataset/{dataset_id}")
        self.id = data.get("id")
        dataset = data.pop("result", {})
        self.load(dataset)

    def __getitem__(self, key):
        return self.data.get(key)

    @property
    def ckan_dataset(self):
        """ Returns the CKAN dataset create from this Superset dataset """
        # TODO
        return None

    def get_chart_data(self):
        """ Get the dataset data """
        return self.superset_instance.get(f"chart/{self.id}/data/")

    def get_chart_file(self, format_):
        """ Download a file from the dataset """
        log.debug(f"Downloading dataset {self.id} as {format_}")
        format_ = format_.lower()
        url = f'chart/{self.id}/data/?format={format_}'
        response = self.superset_instance.get(url, format_=format_)
        log.info(f'RESPONSE: {url} :: {response}')
        log.info(f"Downloaded dataset {self.id} as {format_}: {response.status_code}")
        csv_data = response.content
        return csv_data

    def get_chart_csv(self):
        """ Get the dataset as CSV """
        return self.get_chart_file("csv")

    # TODO get raw data
    # Quizas DATA: /api/v1/chart/ID/data/?format=csv, JSON METADATA + DATA: /api/v1/chart/ID/data/
