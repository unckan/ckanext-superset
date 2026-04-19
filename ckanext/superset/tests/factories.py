"""
Factories for ckanext-superset tests.
"""
import factory
from ckan.tests import factories


class SupersetDataset(factories.Dataset):
    """ A CKAN dataset linked to a Superset chart via the `superset_chart_id` extra. """

    class Params:
        chart_id = '32'

    extras = factory.LazyAttribute(
        lambda o: [{'key': 'superset_chart_id', 'value': str(o.chart_id)}]
    )


class SupersetResource(factories.Resource):
    """ A CSV resource on a Superset-linked dataset. """

    name = 'sync_test.csv'
    format = 'csv'
    url_type = 'upload'
