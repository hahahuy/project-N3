"""Cached streaming access to local nuScenes metadata tables.

The trainval metadata tables are large (``sample_annotation.json`` and
``sample_data.json`` are hundreds of megabytes). Loading them once per scene
makes repeated scene preparation impractical, so this module streams the large
tables exactly once, projects them into a compact local cache and answers scene
scoped queries from that cache.

The cache is a local, private, derived artifact. It never contains raw sensor
data and it is validated against the source table sizes and modification times,
so a changed dataset version rebuilds it instead of serving stale rows.

The index is additive: it does not change ingestion, selection, geometry or any
scientific policy. Callers that keep loading tables directly continue to work.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

INDEX_VERSION = "nuscenes-metadata-index-v1"
SUPPORTED_TABLES = (
    "scene",
    "sample",
    "sample_data",
    "sample_annotation",
    "instance",
    "ego_pose",
    "calibrated_sensor",
    "sensor",
    "category",
)
_SMALL_TABLES = (
    "scene",
    "sample",
    "instance",
    "calibrated_sensor",
    "sensor",
    "category",
)
_BATCH = 5000
_LIDAR_CHANNEL = "LIDAR_TOP"


def default_cache_dir() -> Path:
    """Return the default local metadata cache location."""
    return Path.home() / ".cache" / "real2scenario" / "metadata-index"


class MetadataIndex:
    """Scene scoped, cached read access to local nuScenes metadata."""

    def __init__(
        self,
        dataset_root: str | Path,
        version: str = "v1.0-trainval",
        *,
        cache_dir: str | Path | None = None,
    ) -> None:
        if not version:
            raise ValueError("version must not be empty.")
        self.dataset_root = Path(dataset_root).expanduser().resolve()
        self.version = version
        self.metadata_path = self.dataset_root / version
        if not self.metadata_path.is_dir():
            raise ValueError(f"Dataset metadata directory does not exist: {self.metadata_path}")
        self._signature = _source_signature(self.metadata_path)
        self._lock = threading.RLock()
        self._built_now = False
        self._persistent_cache = cache_dir is not None
        self._cache_path: Path | None = None
        self._connection = self._connect(cache_dir)
        self._small: dict[str, tuple[dict[str, Any], ...]] = {}

    @property
    def index_version(self) -> str:
        return INDEX_VERSION

    @property
    def cache_path(self) -> Path | None:
        return self._cache_path

    @property
    def built_now(self) -> bool:
        return self._built_now

    def status(self) -> dict[str, Any]:
        """Return JSON-safe cache provenance for run cards and reports."""
        return {
            "index_version": INDEX_VERSION,
            "dataset_version": self.version,
            "cache_mode": "persistent" if self._persistent_cache else "in_memory",
            "cache_built_now": self._built_now,
            "source_signature": self._signature,
        }

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def __enter__(self) -> "MetadataIndex":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # Scene queries -----------------------------------------------------

    def scene_records(self) -> tuple[dict[str, Any], ...]:
        """Return every ``scene`` record in source order."""
        return self._small_table("scene")

    def scene(self, scene_token: str) -> dict[str, Any]:
        for record in self.scene_records():
            if record.get("token") == scene_token:
                return record
        raise KeyError(f"Scene {scene_token!r} was not found in {self.metadata_path}.")

    def sample_tokens(self, scene_token: str) -> tuple[str, ...]:
        """Return the ordered keyframe tokens of one scene."""
        samples = self._sample_index()
        scene = self.scene(scene_token)
        tokens: list[str] = []
        current = scene.get("first_sample_token")
        last = scene.get("last_sample_token")
        while isinstance(current, str) and current:
            sample = samples.get(current)
            if sample is None:
                break
            tokens.append(current)
            if current == last:
                return tuple(tokens)
            current = sample.get("next", "")
        raise ValueError(f"Scene {scene_token!r} does not reach its last sample.")

    def instance_tokens(
        self, scene_token: str, *, category_prefix: str | None = "vehicle."
    ) -> tuple[str, ...]:
        """Return sorted instance tokens observed in one scene."""
        rows = self._query(
            "SELECT DISTINCT instance_token FROM scene_instance "
            "WHERE scene_token = ? ORDER BY instance_token",
            (scene_token,),
        )
        if category_prefix is None:
            return tuple(row[0] for row in rows)
        rows = self._query(
            "SELECT DISTINCT instance_token FROM scene_instance "
            "WHERE scene_token = ? AND category_name LIKE ? ORDER BY instance_token",
            (scene_token, f"{category_prefix}%"),
        )
        return tuple(row[0] for row in rows)

    def tables_for_scenes(
        self, scene_tokens: Sequence[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Return ingestion table subsets covering only the requested scenes.

        The result is accepted by :func:`real2scenario.extract_scenario` through
        its ``tables`` argument. Sample chains stay inside the requested scenes,
        LIDAR_TOP keyframes and their ego poses are preserved, and every record
        the ingestion layer can look up is present.
        """
        tokens = tuple(dict.fromkeys(scene_tokens))
        if not tokens:
            raise ValueError("scene_tokens must contain at least one scene token.")
        for token in tokens:
            self.scene(token)
        sample_tokens: set[str] = set()
        for token in tokens:
            sample_tokens.update(self.sample_tokens(token))
        if not sample_tokens:
            raise ValueError("Requested scenes contain no samples.")

        samples = [
            record
            for record in self._small_table("sample")
            if record.get("token") in sample_tokens
        ]
        annotations = self._payload_rows("sample_annotation", "sample_token", sample_tokens)
        instance_tokens = {
            record["instance_token"]
            for record in annotations
            if isinstance(record.get("instance_token"), str)
        }
        instance_records = [
            record
            for record in self._small_table("instance")
            if record.get("token") in instance_tokens
        ]
        category_tokens = {
            record["category_token"]
            for record in instance_records
            if isinstance(record.get("category_token"), str)
        }
        category_records = [
            record
            for record in self._small_table("category")
            if record.get("token") in category_tokens
        ]
        sample_data = self._payload_rows("sample_data", "sample_token", sample_tokens)
        calibration_tokens = {
            record["calibrated_sensor_token"]
            for record in sample_data
            if isinstance(record.get("calibrated_sensor_token"), str)
        }
        calibration_records = [
            record
            for record in self._small_table("calibrated_sensor")
            if record.get("token") in calibration_tokens
        ]
        sensor_tokens = {
            record["sensor_token"]
            for record in calibration_records
            if isinstance(record.get("sensor_token"), str)
        }
        sensor_records = [
            record
            for record in self._small_table("sensor")
            if record.get("token") in sensor_tokens
        ]
        pose_tokens = {
            record["ego_pose_token"]
            for record in sample_data
            if isinstance(record.get("ego_pose_token"), str)
        }
        ego_poses = self._payload_rows("ego_pose", "token", pose_tokens)
        return {
            "scene": [self.scene(token) for token in tokens],
            "sample": samples,
            "sample_data": sample_data,
            "sample_annotation": annotations,
            "instance": instance_records,
            "ego_pose": ego_poses,
            "calibrated_sensor": calibration_records,
            "sensor": sensor_records,
            "category": category_records,
        }

    # Internals ---------------------------------------------------------

    def _connect(self, cache_dir: str | Path | None) -> sqlite3.Connection:
        with self._lock:
            return self._open_cache(cache_dir)

    def _open_cache(self, cache_dir: str | Path | None) -> sqlite3.Connection:
        if cache_dir is None:
            connection = sqlite3.connect(":memory:", check_same_thread=False)
            self._create_schema(connection)
            self._populate(connection)
            return connection
        directory = Path(cache_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.version}-{INDEX_VERSION}.sqlite3"
        if path.exists() and _cache_matches(path, self._signature):
            connection = sqlite3.connect(path, check_same_thread=False)
            self._cache_path = path
            return connection
        temporary = path.with_suffix(".sqlite3.tmp")
        if temporary.exists():
            temporary.unlink()
        connection = sqlite3.connect(temporary, check_same_thread=False)
        self._create_schema(connection)
        self._populate(connection)
        connection.commit()
        connection.close()
        os.replace(temporary, path)
        connection = sqlite3.connect(path, check_same_thread=False)
        self._cache_path = path
        self._built_now = True
        return connection

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE small_table (name TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE sample_annotation (
                sample_token TEXT NOT NULL,
                instance_token TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE sample_data (
                sample_token TEXT NOT NULL,
                ego_pose_token TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE ego_pose (token TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE scene_instance (
                scene_token TEXT NOT NULL,
                instance_token TEXT NOT NULL,
                category_name TEXT NOT NULL
            );
            """
        )

    def _populate(self, connection: sqlite3.Connection) -> None:
        with self._lock:
            self._build_tables(connection)

    def _build_tables(self, connection: sqlite3.Connection) -> None:
        signature = json.dumps(self._signature, sort_keys=True)
        connection.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            (
                ("index_version", INDEX_VERSION),
                ("dataset_version", self.version),
                ("source_signature", signature),
            ),
        )
        small: dict[str, tuple[dict[str, Any], ...]] = {}
        for name in _SMALL_TABLES:
            records = tuple(_read_json_array_path(self.metadata_path / f"{name}.json"))
            small[name] = records
            connection.execute(
                "INSERT INTO small_table (name, payload) VALUES (?, ?)",
                (name, _dump(records)),
            )
        instances = {record.get("token"): record for record in small["instance"]}
        categories = {
            record.get("token"): record.get("name", "") for record in small["category"]
        }
        sensors = {record.get("token"): record for record in small["sensor"]}
        calibrations = {record.get("token"): record for record in small["calibrated_sensor"]}
        sample_scene: dict[str, str] = {}
        for sample in small["sample"]:
            token = sample.get("token")
            if isinstance(token, str):
                sample_scene[token] = str(sample.get("scene_token", ""))

        self._insert_annotations(connection, sample_scene, instances, categories)
        connection.execute(
            "CREATE INDEX sample_annotation_sample ON sample_annotation (sample_token)"
        )
        connection.execute(
            "CREATE INDEX scene_instance_scene ON scene_instance (scene_token)"
        )

        pose_tokens = self._insert_lidar_keyframes(
            connection, sample_scene, calibrations, sensors
        )
        connection.execute("CREATE INDEX sample_data_sample ON sample_data (sample_token)")
        connection.executemany(
            "INSERT INTO ego_pose (token, payload) VALUES (?, ?)",
            _pose_rows(self.metadata_path, pose_tokens),
        )
        connection.commit()

    def _insert_annotations(
        self,
        connection: sqlite3.Connection,
        sample_scene: Mapping[str, str],
        instances: Mapping[Any, Mapping[str, Any]],
        categories: Mapping[Any, Any],
    ) -> None:
        """Stream ``sample_annotation`` once into annotations and scene instances."""
        rows: list[tuple[str, str, str]] = []
        observed: set[tuple[str, str, str]] = set()
        for record in _iter_json_array_records(
            self.metadata_path / "sample_annotation.json"
        ):
            sample_token = record.get("sample_token")
            instance_token = record.get("instance_token")
            if not isinstance(sample_token, str) or not isinstance(instance_token, str):
                continue
            scene_token = sample_scene.get(sample_token)
            if not scene_token:
                continue
            rows.append((sample_token, instance_token, _dump(record)))
            category_name = str(
                categories.get(instances.get(instance_token, {}).get("category_token")) or ""
            )
            key = (scene_token, instance_token, category_name)
            if key not in observed:
                observed.add(key)
                connection.execute(
                    "INSERT INTO scene_instance (scene_token, instance_token, category_name) "
                    "VALUES (?, ?, ?)",
                    key,
                )
            if len(rows) >= _BATCH:
                connection.executemany(
                    "INSERT INTO sample_annotation (sample_token, instance_token, payload) "
                    "VALUES (?, ?, ?)",
                    rows,
                )
                rows.clear()
        if rows:
            connection.executemany(
                "INSERT INTO sample_annotation (sample_token, instance_token, payload) "
                "VALUES (?, ?, ?)",
                rows,
            )

    def _insert_lidar_keyframes(
        self,
        connection: sqlite3.Connection,
        sample_scene: Mapping[str, str],
        calibrations: Mapping[str | None, Mapping[str, Any]],
        sensors: Mapping[str | None, Mapping[str, Any]],
    ) -> set[str]:
        rows: list[tuple[str, str, str]] = []
        pose_tokens: set[str] = set()
        for record in _iter_lidar_keyframes(
            self.metadata_path, calibrations, sensors
        ):
            sample_token = record.get("sample_token")
            pose_token = record.get("ego_pose_token")
            if not isinstance(sample_token, str) or not isinstance(pose_token, str):
                continue
            if sample_scene.get(sample_token) is None:
                continue
            pose_tokens.add(pose_token)
            rows.append((sample_token, pose_token, _dump(record)))
            if len(rows) >= _BATCH:
                connection.executemany(
                    "INSERT INTO sample_data (sample_token, ego_pose_token, payload) "
                    "VALUES (?, ?, ?)",
                    rows,
                )
                rows.clear()
        if rows:
            connection.executemany(
                "INSERT INTO sample_data (sample_token, ego_pose_token, payload) "
                "VALUES (?, ?, ?)",
                rows,
            )
        return pose_tokens

    def _sample_index(self) -> dict[str, dict[str, Any]]:
        records = self._small_table("sample")
        return {str(record["token"]): record for record in records}

    def _small_table(self, name: str) -> tuple[dict[str, Any], ...]:
        if name not in self._small:
            row = self._query(
                "SELECT payload FROM small_table WHERE name = ?", (name,)
            )
            if not row:
                raise ValueError(f"Cached metadata index has no {name!r} table.")
            records = json.loads(row[0][0])
            if not isinstance(records, list):
                raise ValueError(f"Cached {name!r} table is not a JSON array.")
            self._small[name] = tuple(records)
        return self._small[name]

    def _payload_rows(
        self, table: str, column: str, values: Iterable[str]
    ) -> list[dict[str, Any]]:
        wanted = {value for value in values if isinstance(value, str)}
        if not wanted:
            return []
        records: list[dict[str, Any]] = []
        for chunk in _chunks(sorted(wanted), 500):
            placeholders = ",".join("?" for _ in chunk)
            rows = self._query(
                f"SELECT payload FROM {table} WHERE {column} IN ({placeholders})",
                tuple(chunk),
            )
            records.extend(json.loads(row[0]) for row in rows)
        return records

    def _query(self, statement: str, parameters: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("MetadataIndex is closed.")
            return list(self._connection.execute(statement, parameters))


def build_metadata_index(
    dataset_root: str | Path,
    version: str = "v1.0-trainval",
    *,
    cache_dir: str | Path | None = None,
) -> MetadataIndex:
    """Return a metadata index, reusing a matching local cache when possible."""
    return MetadataIndex(dataset_root, version, cache_dir=cache_dir)


# Streaming helpers ----------------------------------------------------


def _iter_lidar_keyframes(
    metadata_path: Path,
    calibrations: Mapping[str | None, Mapping[str, Any]],
    sensors: Mapping[str | None, Mapping[str, Any]],
) -> Iterator[dict[str, Any]]:
    for record in _iter_json_array_records(
        metadata_path / "sample_data.json", needle=_LIDAR_CHANNEL
    ):
        if not record.get("is_key_frame"):
            continue
        calibration = calibrations.get(record.get("calibrated_sensor_token"))
        if not isinstance(calibration, Mapping):
            continue
        sensor = sensors.get(calibration.get("sensor_token"))
        if not isinstance(sensor, Mapping) or sensor.get("channel") != _LIDAR_CHANNEL:
            continue
        yield record


def _pose_rows(
    metadata_path: Path, pose_tokens: set[str]
) -> Iterator[tuple[str, str]]:
    if not pose_tokens:
        return
    for record in _iter_json_array_records(metadata_path / "ego_pose.json"):
        token = record.get("token")
        if isinstance(token, str) and token in pose_tokens:
            yield token, _dump(record)


def _iter_json_array_records(
    path: Path, *, needle: str | None = None
) -> Iterator[dict[str, Any]]:
    """Stream top-level records of a JSON array file with bounded memory.

    Line-delimited top-level arrays (the nuScenes metadata layout) are parsed
    record by record. Any other layout falls back to a single whole-file parse.
    """
    try:
        handle = path.open(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Unable to open dataset metadata {path}: {error}.") from error
    with handle:
        first = handle.readline()
        if first.strip() != "[":
            handle.seek(0)
            yield from _read_json_array(handle, path)
            return
        buffer: list[str] = []
        for line in handle:
            stripped = line.strip()
            if not buffer:
                if stripped == "{":
                    buffer = [line]
                elif stripped in ("]", ""):
                    continue
                else:
                    handle.seek(0)
                    yield from _read_json_array(handle, path)
                    return
                continue
            buffer.append(line)
            if not stripped.startswith("}"):
                continue
            text = "".join(buffer)
            buffer = []
            if needle is not None and needle not in text:
                continue
            record = json.loads(text.rstrip().rstrip(","))
            if isinstance(record, dict):
                yield record
        if buffer:
            record = json.loads("".join(buffer).rstrip().rstrip(","))
            if isinstance(record, dict):
                yield record


def _read_json_array(handle: Any, path: Path) -> list[dict[str, Any]]:
    payload = json.load(handle) if hasattr(handle, "seek") else json.load(
        path.open(encoding="utf-8")
    )
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"Dataset metadata {path} must contain a JSON array of objects.")
    return payload


def _read_json_array_path(path: Path) -> list[dict[str, Any]]:
    return _read_json_array(path.open(encoding="utf-8"), path)


def _source_signature(metadata_path: Path) -> dict[str, dict[str, int]]:
    signature: dict[str, dict[str, int]] = {}
    for name in SUPPORTED_TABLES:
        path = metadata_path / f"{name}.json"
        try:
            stat = path.stat()
        except OSError as error:
            raise ValueError(f"Required dataset metadata is missing: {path}.") from error
        signature[name] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return signature


def _cache_matches(path: Path, signature: Mapping[str, Mapping[str, int]]) -> bool:
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error:
        return False
    try:
        rows = dict(connection.execute("SELECT key, value FROM meta"))
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    except sqlite3.Error:
        return False
    finally:
        connection.close()
    required = {"meta", "small_table", "sample_annotation", "sample_data", "ego_pose", "scene_instance"}
    if not required.issubset(tables) or rows.get("index_version") != INDEX_VERSION:
        return False
    try:
        stored = json.loads(rows.get("source_signature", "{}"))
    except json.JSONDecodeError:
        return False
    return stored == dict(signature)


def _dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _chunks(values: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(values), size):
        yield list(values[start : start + size])