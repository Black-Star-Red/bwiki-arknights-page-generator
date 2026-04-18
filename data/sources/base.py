"""Base data source abstraction."""

from abc import ABC, abstractmethod


class DataSource(ABC):
    """抽象数据源接口。"""

    @abstractmethod
    def load_data(self, config):
        """加载数据，返回统一格式的字典。"""


__all__ = ["DataSource"]

