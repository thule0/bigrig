"""
Objects representing repos that store python distributions
"""

import os.path

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

    def project(self):
        raise NotImplementedError

    def project_files(self, project):
        raise NotImplementedError

    def download(self, project, file, dest):
        raise NotImplementedError

    def upload(self, project, file):
        raise NotImplementedError

    def download_sdist(self, project, version, dir):
        sdists = [
            dist
            for dist in self.project_files(project)
            if dist.package_type == "sdist" and dist.version == version
        ]
        if not sdists:
            raise NotAvailable(f"No sdists for {project}={version}")
        sdist = sdists[0]
        return self.download(project, sdist[0].filename)


class SimpleRepo(PythonDistributionRepo):
    """ PEP-503 (aka pypi/simple) compliant repository """

    def __init__(self, url, auth=None):
        self.url = url
        self._username, self._password = auth or (None, None)
        self.client = PyPISimple(endpoint=url)

    def project_files(self, project):
        return self.client.get_project_files(project)

    def download(self, project, file, dest):
        dists = [x for x in self.project_files(project) if x.filename == file]
        if not dists:
            raise NotAvailable(f"{file} is not available in project{project}")
        dist = dists[0]
        full_fname = os.path.join(dest, dist.filename)
        download_file(dist.url, full_fname)
        return full_fname

    def upload(self, project, file):
        settings = twine.settings.Settings(
            repository_url=self.url, username=self._username, password=self._password
        )
        # TODO: use twine Repository object instead of command?
        twine_upload(settings, [file])


class LocalRepo(PythonDistributionRepo):
    def __init__(self, path):
        self.path = path

    # TODO
