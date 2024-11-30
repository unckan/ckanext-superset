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
