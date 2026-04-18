"""JSON data source."""

import json
import os

from .base import DataSource


class JsonDataSource(DataSource):
    """本地 JSON 文件数据源。"""

    def load_data(self, config):
        file_path = config["file_path"]
        encoding = config.get("encoding", "utf-8")

        # 新结构下优先相对项目根目录解析，而不是 data/sources 目录。
        if not os.path.isabs(file_path):
            relative_path = file_path
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            file_path = os.path.join(project_root, relative_path)

            if not os.path.exists(file_path):
                alt_path = os.path.join(os.getcwd(), relative_path)
                if os.path.exists(alt_path):
                    file_path = alt_path
                else:
                    alt_path = os.path.join(os.getcwd(), "ArknightsGameData", relative_path)
                    if os.path.exists(alt_path):
                        file_path = alt_path

        with open(file_path, "r", encoding=encoding) as f:
            data = json.load(f)

        if config.get("unpack_keys", False):
            key_column = config.get("key_column", "key")
            if isinstance(data, dict):
                return data
            return {item.get(key_column, str(i)): item for i, item in enumerate(data)}

        return data


__all__ = ["JsonDataSource"]

