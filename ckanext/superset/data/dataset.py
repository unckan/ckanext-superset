import logging


log = logging.getLogger(__name__)


class SupersetDataset:
    """ An Apache Superset dataset """

    def __init__(self):
        self.id = None
        self.data = {}

    def load(self, json_data):
        """ Load the dataset from a JSON object
        See /ckanext/superset/data/samples/dataset.json
        """
        self.data = json_data
        self.id = json_data.get("id")

    def __getitem__(self, key):
        return self.data.get(key)

    # TODO get raw data
    # Quizas DATA: /api/v1/chart/ID/data/?format=csv, JSON METADATA + DATA: /api/v1/chart/ID/data/
