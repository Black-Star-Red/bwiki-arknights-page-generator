"""JSON data source."""

import json
import os

from .base import DataSource


class JsonDataSource(DataSource):
    """本地 JSON 文件数据源。"""

    def _project_root(self):
        # json_source.py 在 data/sources 下，回退 3 层到 arknights_toolbox
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    def _resolve_file_path(self, config):
        file_path = config["file_path"]
        data_root = config.get("data_root")
        # 绝对路径直接用
        if os.path.isabs(file_path):
            return file_path
        candidates = []
        project_root = self._project_root()
        # 新结构：data_root + file_path
        if data_root:
            if os.path.isabs(data_root):
                candidates.append(os.path.join(data_root, file_path))
            else:
                candidates.append(os.path.join(project_root, data_root, file_path))
                candidates.append(os.path.join(os.getcwd(), data_root, file_path))
        # 旧结构兼容：file_path 自带完整相对前缀
        candidates.append(os.path.join(project_root, file_path))
        candidates.append(os.path.join(os.getcwd(), file_path))
        candidates.append(os.path.join(os.getcwd(), "ArknightsGameData", file_path))
        for p in candidates:
            if os.path.exists(p):
                return p
        # 兜底返回第一个候选，便于报错时定位
        return candidates[0] if candidates else file_path
    def load_data(self, config):
        file_path = self._resolve_file_path(config)
        encoding = config.get("encoding", "utf-8")
        with open(file_path, "r", encoding=encoding) as f:
            data = json.load(f)
        if config.get("unpack_keys", False):
            key_column = config.get("key_column", "key")
            if isinstance(data, dict):
                return data
            return {item.get(key_column, str(i)): item for i, item in enumerate(data)}
        return data


__all__ = ["JsonDataSource"]

