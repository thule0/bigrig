import os
import typing as t
from dataclasses import dataclass
from itertools import zip_longest
from packaging.requirements import Requirement

import yaml
import jsonschema

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
                "variables": {
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
            "required": ["variables", "location"],
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Origin):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return self.location == other.location and self.credentials == other.credentials


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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Credentials):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return self.username == other.username and self.password == other.password


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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Source):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return self.location == other.location and self.credentials == other.credentials


@dataclass
class Target:
    location: str
    variables: t.Dict[str, t.Any]
    credentials: t.Optional["Credentials"]

    @classmethod
    def from_dict(cls, blob: t.Dict) -> "Target":
        return cls(
            location=blob["location"],
            variables=blob["variables"],
            credentials=Credentials.from_path(path=blob.get("credentialsPath")),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Target):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return (
            self.location == other.location
            and self.variables == other.variables
            and self.credentials == other.credentials
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfigEntry):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return (
            self.origin == other.origin
            and self.source == other.source
            and self.targets == other.targets
        )


@dataclass
class RootConfig:
    entry: ConfigEntry
    packages: t.List[Requirement]

    @classmethod
    def get_instance(cls) -> "RootConfig":
        config_path = os.environ.get("BIGRIG_CONFIG_PATH")
        if not config_path:
            raise ValueError(
                f"Missing path to bigrig configuration, point BIGRIG_CONFIG_PATH to bigrig"
                f"configuration file"
            )

        packages_path = os.environ.get("BIGRIG_PACKAGES_PATH")
        if not packages_path:
            raise ValueError(
                f"Missing path to bigrig package list, point BIGRIG_PACKAGES_PATH to bigrig"
                f"package file list"
            )

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

        return cls(entry=entry, packages=packages)

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
            and self.entry == other.entry
        )


class Settings:
    root: RootConfig

    def __getattribute__(self, name: str) -> t.Any:
        try:
            return super().__getattribute__(name)
        except AttributeError as exc:
            if name == "root":
                raise ImportError(
                    f"Application is improperly configured. Before accessing 'settings.{name}'"
                    f" '{__name__}.settings.configure()' needs to called"
                ) from exc
            raise

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Settings):
            raise TypeError(
                f"'==' not supported between instances of '{self.__class__.__name__}' and"
                f" '{other.__class__.__name__}'"
            )
        return self.root == other.root

    def __repr__(self) -> str:
        try:
            return f"{self.__class__.__name__}(root='{self.root}')"
        except ImportError:
            return f"{self.__class__.__name__}(<Unconfigured>)"

    def configure(self) -> None:
        try:
            # Trigger attribute checks
            self.root
        except ImportError:
            # `root` object is missing, configure it
            super().__setattr__("root", RootConfig.get_instance())
        else:
            # `root` object is present, we're calling `configure` 1+ times
            raise RuntimeError(
                f"Settings already have been configured once. A duplicate call to"
                f" '{__name__}.settings.configure()' exists somewhere in the code path"
            )


settings = Settings()


settings = Settings()
