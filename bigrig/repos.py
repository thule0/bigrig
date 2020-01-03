"""
Objects representing repos that store python distributions
"""
import os.path
import typing as t

import twine.settings
from pypi_simple import PyPISimple
from twine.commands.upload import upload as twine_upload

from .exceptions import NotAvailable
from .utils import download_file

__all__ = ["LocalRepo", "SimpleRepo", "PythonDistributionRepo"]


class PythonDistributionRepo:
    """
    A place where python distribution files are stored
    """

    def project(self) -> t.Any:
        raise NotImplementedError

    def project_files(self, project: t.Any) -> t.Any:
        raise NotImplementedError

    def download(self, project: t.Any, file: t.Any, dest: t.Any) -> t.Any:
        raise NotImplementedError

    def upload(self, project: t.Any, file: t.Any) -> t.Any:
        raise NotImplementedError

    def download_sdist(self, project: t.Any, version: t.Any, dir: t.Any) -> t.Any:
        sdists = [
            dist
            for dist in self.project_files(project)
            if dist.package_type == "sdist" and dist.version == version
        ]
        if not sdists:
            raise NotAvailable(f"No sdists for {project}={version}")
        sdist = sdists[0]
        # FIXME download `dest` is wrong, added to pass mypy checks
        return self.download(project, sdist[0].filename, dest=None)


class SimpleRepo(PythonDistributionRepo):
    """ PEP-503 (aka pypi/simple) compliant repository """

    _username: t.Optional[str]
    _password: t.Optional[str]
    url: str
    client: PyPISimple

    def __init__(self, url: str, auth: t.Tuple[str, str] = None) -> None:
        self.url = url
        self._username, self._password = auth or (None, None)
        self.client = PyPISimple(endpoint=url)

    def project_files(self, project: t.Any) -> t.Any:
        return self.client.get_project_files(project)

    def download(self, project: t.Any, file: t.Any, dest: t.Any) -> t.Any:
        dists = [x for x in self.project_files(project) if x.filename == file]
        if not dists:
            raise NotAvailable(f"{file} is not available in project{project}")
        dist = dists[0]
        full_fname = os.path.join(dest, dist.filename)
        download_file(dist.url, full_fname)
        return full_fname

    def upload(self, project: t.Any, file: t.Any) -> t.Any:
        settings = twine.settings.Settings(
            repository_url=self.url, username=self._username, password=self._password
        )
        # TODO: use twine Repository object instead of command?
        twine_upload(settings, [file])


class LocalRepo(PythonDistributionRepo):
    path: str

    def __init__(self, path: str) -> None:
        self.path = path

    # TODO
