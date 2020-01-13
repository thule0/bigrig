import dataclasses
import os
import typing as t
from dataclasses import dataclass
from itertools import zip_longest

import jsonschema
import yaml
from packaging.requirements import Requirement

from bigrig.exceptions import SettingsNotConfigured

__all__ = ["settings"]

CREDENTIALS_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string", "minLength": 1},
        "password": {"type": "string"},
    },
    "required": ["username", "password"],
    "additionalProperties": False,
}

CONFIG_SCHEMA = {
    "type": "object",
    "definitions": {
        "origin": {
            "type": "object",
            "description": (
                "This is basically big public Pypi, where we get initial sources from. It may be"
                " external"
            ),
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Local FS folder or url to pypi simple compatible repo",
                },
                "credentialsPath": {
                    "type": "string",
                    "description": "Path to YAML file containing CREDENTIALS_SCHEMA",
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
        "source": {
            "type": "object",
            "description": (
                "where we put sources fetched from origin for internal keeping. Need only one"
                " of those"
            ),
            "properties": {
                "location": {
                    "type": "string",
                    "description": "url to pypi simple compatible repo",
                },
                "credentialsPath": {
                    "type": "string",
                    "description": "Path to YAML file containing CREDENTIALS_SCHEMA",
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
        "target": {
            "type": "object",
            "properties": {
                "vars": {
                    "type": "object",
                    "description": (
                        "Variables to be forwarded to the dockerfile template and used inside"
                    ),
                },
                "location": {
                    "type": "string",
                    "description": "url to pypi simple compatible repo",
                },
                "credentialsPath": {
                    "type": "string",
                    "description": "Path to YAML file containing CREDENTIALS_SCHEMA",
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    },
    "properties": {
        "origin": {"$ref": "#/definitions/origin"},
        "source": {"$ref": "#/definitions/source"},
        "targets": {
            "type": "object",
            "description": (
                "where we put the built things. As many as we have arches + pythonversions ("
                " or maybe just arches? You can have several pythonversions coexist in one repo)"
            ),
            "patternProperties": {"^[a-z0-9_]+$": {"$ref": "#/definitions/target"}},
        },
    },
    "required": ["origin", "source", "targets"],
    "additionalProperties": False,
}


@dataclass
class Origin:
    location: str
    credentials: t.Optional["Credentials"]

    @classmethod
    def from_dict(cls, blob: t.Dict) -> "Origin":
        return cls(
            location=blob["location"],
            credentials=Credentials.from_path(path=blob.get("credentialsPath")),
        )


@dataclass
class Credentials:
    username: str
    password: str

    @classmethod
    def from_path(cls, path: t.Optional[str]) -> t.Optional["Credentials"]:
        if not path:
            return None

        try:
            with open(path, "rt") as fid:
                credentials = yaml.safe_load(fid)
        except yaml.YAMLError:
            # Raise from None to avoid accidental leaks
            raise yaml.YAMLError(
                f"Unable to load credentials from '{path}', it appears to be a non-yaml file"
            ) from None
        except OSError as exc:
            raise OSError(f"Unable to load credentials from '{path}'") from exc

        # As these are loaded later, a runtime validation is needed
        jsonschema.validate(instance=credentials, schema=CREDENTIALS_SCHEMA)

        return cls(username=credentials["username"], password=credentials["password"])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(username='{self.username}', password='***')"


@dataclass
class Source:
    location: str
    credentials: t.Optional["Credentials"]

    @classmethod
    def from_dict(cls, blob: t.Dict) -> "Source":
        return cls(
            location=blob["location"],
            credentials=Credentials.from_path(path=blob.get("credentialsPath")),
        )


@dataclass
class Target:
    location: str
    vars: t.Dict[str, t.Any]
    credentials: t.Optional["Credentials"]

    @classmethod
    def from_dict(cls, blob: t.Dict) -> "Target":
        return cls(
            location=blob["location"],
            vars=blob["vars"],
            credentials=Credentials.from_path(path=blob.get("credentialsPath")),
        )


@dataclass
class ConfigEntry:
    origin: Origin
    source: Source
    targets: t.Dict[str, Target]

    @classmethod
    def from_dict(cls, blob: t.Dict) -> "ConfigEntry":
        jsonschema.validate(instance=blob, schema=CONFIG_SCHEMA)
        return cls(
            origin=Origin.from_dict(blob["origin"]),
            source=Source.from_dict(blob["source"]),
            targets={
                name: Target.from_dict(target)
                for name, target in blob["targets"].items()
            },
        )


@dataclass
class RootConfig:
    config: ConfigEntry
    packages: t.List[Requirement]

    @classmethod
    def from_dir(cls, config_dir: str):
        packages_path = os.path.join(config_dir, "packages.txt")
        config_path = os.path.join(config_dir, "config.yaml")

        try:
            with open(config_path, "rt") as fid:
                entry = ConfigEntry.from_dict(blob=yaml.safe_load(fid))
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(
                f"Unable to load config from '{config_path}', it appears to be a non-yaml file"
            ) from exc
        except OSError as exc:
            raise OSError(f"Unable to load config from '{config_path}'") from exc

        try:
            with open(packages_path, "rt") as fid:
                packages = [Requirement(package) for package in fid]
        except OSError as exc:
            raise OSError(f"Unable to load packages from '{packages_path}'") from exc

        return cls(config=entry, packages=packages)

    def all_settings(self):
        fields = [f.name for f in dataclasses.fields(self.config)]
        return {
            **{f: getattr(self.config, f) for f in fields},
            "packages": self.packages,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RootConfig):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return (
            all(
                str(self_pkg) == str(other_pkg)
                for self_pkg, other_pkg in zip_longest(self.packages, other.packages)
            )
            and self.config == other.config
        )


class Settings:
    _wrapped: dict = None
    _config_dir: str = None

    @property
    def configured(self):
        return self._wrapped is not None

    def __getattr__(self, name: str) -> t.Any:
        if not self.configured:
            raise SettingsNotConfigured(
                f"Application is not configured. Call '{__name__}.settings.configure() before accessing settings"
            )
        return self._wrapped[name]

    def __repr__(self) -> str:
        if self._config_dir is not None:
            return f"{self.__class__.__name__}({self._config_dir})"
        elif self.configured:
            return f"{self.__class__.__name__}"
        else:
            return f"{self.__class__.__name__}(<Unconfigured>)"

    def configure(self, config_dir=None) -> None:
        config_dir = config_dir or os.environ.get("BIGRIG_CONFIG_PATH")
        if not config_dir:
            raise ValueError(
                f"Missing path to bigrig configuration, point BIGRIG_CONFIG_PATH to bigrig"
                f"configuration file"
            )

        root = RootConfig.from_dir(config_dir)
        self._wrapped = {**root.all_settings()}
        self._config_dir = config_dir


settings = Settings()
