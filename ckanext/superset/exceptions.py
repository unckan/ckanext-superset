class SupersetRequestException(Exception):
    """ Superset could not answer a request.

    `status_code` is the HTTP status CKAN should answer with: CKAN acts as a
    gateway to Superset, so a failure upstream is a 502 (Bad Gateway) and a
    timeout is a 504 (Gateway Timeout), never a 500.
    """

    def __init__(self, message='', status_code=502):
        super().__init__(message)
        self.status_code = status_code
