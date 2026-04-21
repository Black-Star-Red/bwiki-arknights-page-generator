"""Data mapper implementation."""

import datetime
import json
import operator as op
import os
import re
from pathlib import Path
from .sources import ApiDataSource, FileDataSource, JsonDataSource
from contextlib import contextmanager

class DataMapper:
    """数据映射器，负责统一访问不同数据源。"""

    def __init__(
        self,
        config_path,
        debug=False,
        log_path=None,
        data_source_group=None,
        interactive=None,
    ):
        if hasattr(self, "config_path"):
            return

        self.config_path = config_path
        self.config = self._load_config()
        self.sources = {}
        self.data_cache = {}
        self.mappings = {}
        self.value_maps = {}
        self.field_meta = {}
        self.schema = self.config.get("schema", {})
        self.debug = bool(debug)
        self.log_path = log_path
        self._requested_data_source_group = data_source_group
        # None 时根据 stdin 自动推断；GUI/非交互场景会走自动选择而非 input。
        self._interactive = interactive
        self.run_id = None
        self.current_data_sources = None
        self._init_sources()

    def _project_root(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _log(self, level, message, **kv):
        if not self.debug and level not in ("ERROR",):
            return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        extra = ""
        if kv:
            extra = " " + " ".join(f"{k}={v!r}" for k, v in kv.items())
        line = f"[{ts}] [{level}] {message}{extra}"
        try:
            print(line)
        except Exception:
            pass
        if self.log_path:
            try:
                log_dir = os.path.dirname(os.path.abspath(self.log_path))
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def set_debug(self, debug=True, log_path=None):
        self.debug = bool(debug)
        if log_path is not None:
            self.log_path = log_path

    def _read_config_file(self, path_obj: Path):
        suffix = path_obj.suffix.lower()
        if suffix == ".json":
            return json.loads(path_obj.read_text(encoding="utf-8"))
        if suffix in {".yaml", ".yml"}:
                    try:
                        import yaml
                    except ImportError as e:
                        raise RuntimeError(
                            f"配置文件是 YAML，但未安装 PyYAML: {path_obj}\n"
                            "请安装: pip install pyyaml"
                        ) from e
                    with path_obj.open("r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
        raise RuntimeError(f"不支持的配置格式: {path_obj}")
    def load_merged_config(self, base_path: Path):
        base = self._read_config_file(base_path)
        # 关键：按主配置后缀找 local
        local_name = f"{base_path.stem}.local{base_path.suffix}"  # config.local.json / config.local.yaml
        local_path = base_path.with_name(local_name)
        if local_path.exists():
            local = self._read_config_file(local_path)
            base.update(local)  # 需要深合并可替换这里
        env_cookies = os.getenv("ARK_TOOL_COOKIES")
        if env_cookies:
            base["cookies"] = env_cookies
        return base
    def _load_config(self):
        if not os.path.isabs(self.config_path):
            root = self._project_root()
            rel_path = self.config_path
            # 新结构默认从 arknights_toolbox/config 读取配置。
            candidates = [
                os.path.join(root, "arknights_toolbox", "config", rel_path),
                os.path.join(root, rel_path),
                os.path.join(os.getcwd(), rel_path),
                os.path.join(os.getcwd(), "ArknightsGameData", rel_path),
            ]
            config_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
        else:
            config_path = self.config_path

        path_obj = Path(config_path)
        # JSON / 其它默认走你的合并逻辑
        return self.load_merged_config(path_obj)

    def _init_sources(self):
        mapping_sources = {}
        data_sources = self.config.get("data_sources", {})
        for i, key in enumerate(data_sources):
            self._log("DEBUG", "data_source_option", index=i, key=key)
            mapping_sources[i] = key

        if not mapping_sources:
            raise ValueError("没有可用的数据源")

        # 1) 外部显式指定（GUI/CLI 传入）优先
        if self._requested_data_source_group:
            if self._requested_data_source_group not in data_sources:
                raise ValueError(f"Unknown data source group: {self._requested_data_source_group}")
            self.current_data_sources = self._requested_data_source_group
        else:
            # 2) 未显式指定时：交互模式才 input；否则自动选第一个
            interactive = self._interactive
            if interactive is None:
                try:
                    import sys

                    interactive = bool(hasattr(sys.stdin, "isatty") and sys.stdin.isatty())
                except Exception:
                    interactive = False

            if interactive:
                index_key = input("请输入使用数据源(下标):")
                self.current_data_sources = mapping_sources[int(index_key)]
            else:
                self.current_data_sources = next(iter(data_sources.keys()))

        if self.current_data_sources is None:
            raise ValueError("没有可用的数据源")

        for source_config in data_sources[self.current_data_sources]:
            source_id = source_config["id"]
            source_type = source_config["type"]

            if source_type == "json":
                self.sources[source_id] = JsonDataSource()
            elif source_type == "api":
                self.sources[source_id] = ApiDataSource()
            elif source_type == "file":
                self.sources[source_id] = FileDataSource()
            else:
                raise ValueError(f"Unsupported data source type: {source_type}")

            self.mappings[source_id] = source_config.get("field_mappings", {})
            self.value_maps[source_id] = source_config.get("value_maps", {})
            self.field_meta[source_id] = source_config.get("field_meta", {})

    def _check_type(self, value, type_spec):
        if type_spec is None:
            return True
        if type_spec == "string":
            return isinstance(value, str)
        if type_spec == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if type_spec == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if type_spec == "bool":
            return isinstance(value, bool)
        if type_spec.startswith("list[") and type_spec.endswith("]"):
            if not isinstance(value, list):
                return False
            inner = type_spec[5:-1]
            return all(self._check_type(v, inner) for v in value)
        return True

    def validate_field_meta(self, source_id, sample_ids=None, sample_size=3):
        issues = []
        meta = self.schema.get(source_id) or self.field_meta.get(source_id) or {}
        if not meta:
            return issues

        ids = sample_ids
        if ids is None and "charIdS" in self.mappings.get(source_id, {}):
            ids = self.get_data_safe(source_id, "charIdS", default=[]) or []
        ids = list(ids or [])[:sample_size]

        for field_name, rule in meta.items():
            kind = rule.get("kind")
            required = bool(rule.get("required", False))
            type_spec = rule.get("type")
            enum_vals = rule.get("enum")
            path = rule.get("path", field_name)

            if kind == "var":
                v = self.mappings.get(source_id, {}).get(field_name)
                if required and (v is None or v == ""):
                    issues.append(f"[{source_id}] var '{field_name}' is required but empty")
                continue

            values = []
            if "{currentCharId}" in self.mappings.get(source_id, {}).get(path, "") or path in (
                "rarity",
                "talent_phase",
            ):
                for cid in ids:
                    self.add_mapping(source_id, "currentCharId", cid)
                    if field_name == "talent_phase":
                        self.add_mapping(source_id, "talent_group_index", "0")
                        self.add_mapping(source_id, "talent_candidate_index", "0")
                    values.append(self.get_data_safe(source_id, path, default=None))
            else:
                values.append(self.get_data_safe(source_id, path, default=None))

            if required and all(v is None or v == "" or v == [] for v in values):
                issues.append(f"[{source_id}] field '{field_name}' is required but all sampled values are empty")
                continue

            for v in values:
                if v is None:
                    continue
                if type_spec and not self._check_type(v, type_spec):
                    issues.append(
                        f"[{source_id}] field '{field_name}' type mismatch: expect {type_spec}, got {type(v).__name__}"
                    )
                    break
                if enum_vals and v not in enum_vals:
                    issues.append(f"[{source_id}] field '{field_name}' enum mismatch: {v!r} not in {enum_vals}")
                    break

        return issues

    def _apply_value_map(self, source_id, field_path, value):
        vm_all = self.value_maps.get(source_id) or {}
        if not vm_all or field_path is None:
            return value
        table = vm_all.get(field_path)
        if not table:
            return value
        if value is None:
            return value
        for k in (value, str(value), str(value).strip()):
            if k in table:
                return table[k]
        return value

    def get_data(self, source_id, field_path=None, refresh=False):
        if source_id not in self.sources:
            raise ValueError(f"Unknown data source: {source_id}")

        if refresh or source_id not in self.data_cache:
            source_config = next(s for s in self.config["data_sources"][self.current_data_sources] if s["id"] == source_id)
            self.data_cache[source_id] = self.sources[source_id].load_data(source_config["config"])

        data = self.data_cache[source_id]
        if field_path:
            if field_path in self.mappings[source_id]:
                actual_path = self.mappings[source_id][field_path]
            else:
                actual_path = field_path
            result = self._get_nested_value(data, actual_path, source_id)
            return self._apply_value_map(source_id, field_path, result)
        return data

    def get_data_safe(self, source_id, field_path=None, default=None, refresh=False):
        try:
            return self.get_data(source_id, field_path, refresh)
        except (ValueError, KeyError, IndexError, TypeError):
            self._log("DEBUG", "cannot_access_path", source_id=source_id, field_path=field_path, default=default)
            return default

    def has_path(self, source_id, field_path, refresh=False):
        try:
            self.get_data(source_id, field_path, refresh)
            return True
        except (ValueError, KeyError, IndexError, TypeError):
            return False

    def _get_nested_value(self, data, path, source_id=None):
        if not path:
            return data
        if path == "forKey":
            return list(data.keys()) if isinstance(data, dict) else []

        m = re.match(r"^\s*(.+?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)\s*$", path)
        if m:
            base_path, sym, num_str = m.group(1), m.group(2), m.group(3)
            base_val = self._get_nested_value(data, base_path, source_id)
            if isinstance(base_val, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", base_val.strip()):
                base_val = float(base_val) if "." in base_val else int(base_val)
            if not isinstance(base_val, (int, float)):
                raise ValueError(f"Value at '{base_path}' is not numeric, cannot do '{sym}{num_str}': {base_val!r}")
            num = float(num_str) if "." in num_str else int(num_str)
            ops = {"+": op.add, "-": op.sub, "*": op.mul, "/": op.truediv}
            return ops[sym](base_val, num)

        parts = path.split(".")

        def process(segments, current):
            if not segments:
                return current
            segment = segments[0]
            rest = segments[1:]

            if source_id:
                while "{" in segment and "}" in segment:
                    start = segment.find("{")
                    end = segment.find("}", start)
                    if end == -1:
                        break
                    var_name = segment[start + 1 : end]
                    mapping = self.mappings.get(source_id, {})
                    if var_name not in mapping:
                        raise ValueError(f"Variable '{var_name}' not found in mappings for source_id {source_id}")
                    replacement = str(mapping[var_name])
                    segment = segment[:start] + replacement + segment[end + 1 :]

            if "[" in segment:
                bracket_pos = segment.find("[")
                key_name = segment[:bracket_pos]
                indices_str = segment[bracket_pos:]
                indices = re.findall(r"\[([^\]]*)\]", indices_str)
            else:
                key_name = segment
                indices = []

            if key_name == "":
                intermediate = current
            else:
                if isinstance(current, dict) and segment in current:
                    intermediate = current[segment]
                    indices = []
                elif "." in key_name and isinstance(current, dict):
                    if key_name in current:
                        intermediate = current[key_name]
                    else:
                        sub_parts = key_name.split(".")
                        intermediate = process(sub_parts, current)
                else:
                    try:
                        intermediate = current[key_name]
                    except (KeyError, TypeError) as e:
                        self._log(
                            "DEBUG",
                            "segment_access_failed",
                            path=path,
                            segment=segment,
                            key=key_name,
                            current_type=str(type(current)),
                            err=str(e),
                        )
                        raise ValueError(f"Key '{key_name}' not found in data at path segment '{segment}'") from e

            for i, idx in enumerate(indices):
                if idx == "*":
                    if not isinstance(intermediate, list):
                        raise ValueError(
                            f"Expected list at path segment '{segment}' with wildcard '*', but got {type(intermediate)}"
                        )
                    remaining_indices = indices[i + 1 :]
                    if remaining_indices:
                        remaining_segment = "".join(f"[{x}]" for x in remaining_indices)
                        new_rest = [remaining_segment] + rest
                    else:
                        new_rest = rest
                    return [self._get_nested_value(item, ".".join(new_rest), source_id) for item in intermediate]

                if ":" in idx:
                    if not isinstance(intermediate, list) and not isinstance(intermediate, str):
                        raise ValueError(
                            f"Expected list at path segment '{segment}' with slice '{idx}', but got {type(intermediate)}"
                        )
                    parts = idx.split(":")
                    if len(parts) > 3:
                        raise ValueError(f"Slice '{idx}' invalid at path segment '{segment}'")

                    def to_int_or_none(x):
                        if x == "":
                            return None
                        try:
                            return int(x)
                        except ValueError as e:
                            raise ValueError(f"Slice '{idx}' invalid at path segment '{segment}'") from e

                    slice_obj = slice(*(to_int_or_none(p) for p in parts))
                    intermediate = intermediate[slice_obj]
                    continue

                try:
                    idx_int = int(idx)
                    intermediate = intermediate[idx_int]
                except (ValueError, IndexError, TypeError) as e:
                    raise ValueError(f"Index '{idx}' invalid at path segment '{segment}'") from e

            if rest:
                return self._get_nested_value(intermediate, ".".join(rest), source_id)
            return intermediate

        return process(parts, data)

    def get_all_sources(self):
        return list(self.sources.keys())

    def clear_cache(self, source_id=None):
        if source_id:
            self.data_cache.pop(source_id, None)
        else:
            self.data_cache.clear()

    def _install_data_sources_group(self, group_key):
        """Install a data source group without interactive prompts."""
        data_sources = self.config.get("data_sources", {}) or {}
        if group_key not in data_sources:
            raise ValueError(f"Unknown data source group: {group_key}")

        self.current_data_sources = group_key
        self.sources = {}
        self.data_cache = {}
        self.mappings = {}
        self.value_maps = {}
        self.field_meta = {}

        for source_config in data_sources[group_key]:
            source_id = source_config["id"]
            source_type = source_config["type"]

            if source_type == "json":
                self.sources[source_id] = JsonDataSource()
            elif source_type == "api":
                self.sources[source_id] = ApiDataSource()
            elif source_type == "file":
                self.sources[source_id] = FileDataSource()
            else:
                raise ValueError(f"Unsupported data source type: {source_type}")

            self.mappings[source_id] = source_config.get("field_mappings", {})
            self.value_maps[source_id] = source_config.get("value_maps", {})
            self.field_meta[source_id] = source_config.get("field_meta", {})

    @contextmanager
    def temporary_source_group(self, group_key):
        """
        Temporarily switch to another configured source group.

        The previous mapper state (group, mappings and caches) will be restored
        after leaving the context.
        """
        prev_group = self.current_data_sources
        prev_requested = self._requested_data_source_group
        prev_sources = self.sources
        prev_cache = self.data_cache
        prev_mappings = self.mappings
        prev_value_maps = self.value_maps
        prev_field_meta = self.field_meta

        # Temporarily disable fixed-group selection to allow explicit switch.
        self._requested_data_source_group = None
        self._install_data_sources_group(group_key)
        try:
            yield
        finally:
            self.current_data_sources = prev_group
            self._requested_data_source_group = prev_requested
            self.sources = prev_sources
            self.data_cache = prev_cache
            self.mappings = prev_mappings
            self.value_maps = prev_value_maps
            self.field_meta = prev_field_meta

    def add_mapping(self, source_id, field_name, field_path):
        if source_id not in self.mappings:
            self.mappings[source_id] = {}
        self.mappings[source_id][field_name] = field_path

    def set_run_context(self, run_id):
        self.run_id = run_id

    def flush_missing_path_summary(self):
        # 与脚本接口对齐：当前实现暂不聚合 missing path，保留空实现避免流程中断。
        return None


__all__ = ["DataMapper"]

