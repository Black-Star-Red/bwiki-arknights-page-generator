"""Generic file data source."""

from .base import DataSource
from .json_source import JsonDataSource


class FileDataSource(DataSource):
    """通用文件数据源（可扩展支持其他格式）。"""

    def load_data(self, config):
        file_type = config.get("file_type", "json")
        if file_type == "json":
            return JsonDataSource().load_data(config)
        raise ValueError(f"Unsupported file type: {file_type}")


__all__ = ["FileDataSource"]

