"""API data source."""

import requests

from .base import DataSource


class ApiDataSource(DataSource):
    """外部 API 数据源。"""

    def load_data(self, config):
        url = config["url"]
        headers = config.get("headers", {})
        params = config.get("params", {})
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


__all__ = ["ApiDataSource"]

