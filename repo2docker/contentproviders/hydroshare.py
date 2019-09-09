import zipfile
import os
import shutil
import time

from urllib.request import urlopen, Request, urlretrieve
from urllib.error import HTTPError

from .base import ContentProvider
from ..utils import normalize_doi, is_doi


class Hydroshare(ContentProvider):
    """Provide contents of a Hydroshare resource."""

    def _urlopen(self, req, headers=None):
        """A urlopen() helper"""
        conn = urlopen(req)
        while conn.info().get_content_type() != "application/zip":
            if conn.getcode() != 200:
                yield "Failed to download bag. status code {}.\n".format(conn.getcode())
                return
            wait_time = 10
            yield "Bag is being prepared, requesting again in {} seconds.\n".format(wait_time)
            time.sleep(wait_time)
            conn = urlopen(req)

        # Bag creation seems to need a small time buffer after it says it's ready.
        time.sleep(1)
        return urlopen(req)

    def _doi2url(self, doi):
        # Transform a DOI to a URL
        # If not a doi, assume we have a URL and return
        if is_doi(doi):
            doi = normalize_doi(doi)

            try:
                resp = self._urlopen("https://doi.org/{}".format(doi))
            # If the DOI doesn't resolve, just return URL
            except HTTPError:
                return doi
            return resp.url
        else:
            # Just return what is actulally just a URL
            return doi

    def detect(self, doi, ref=None, extra_args=None):
        """Trigger this provider for things that resolve to a Zenodo/Invenio record"""
        # We need the hostname (url where records are), api url (for metadata),
        # filepath (path to files in metadata), filename (path to filename in
        # metadata), download (path to file download URL), and type (path to item type in metadata)
        hosts = [
            {
                "hostname": ["https://www.hydroshare.org/resource/", "http://www.hydroshare.org/resource/"],
                "django_irods": "https://www.hydroshare.org/django_irods/download/bags/",
            },
        ]

        url = self._doi2url(doi)

        for host in hosts:
            if any([url.startswith(s) for s in host["hostname"]]):
                self.resource_id = url.strip("/").rsplit("/", maxsplit=1)[1]
                return {"resource": self.resource_id, "host": host}

    def fetch(self, spec, output_dir, yield_output=False):
        """Fetch and unpack a Hydroshare resource"""
        resource_id = spec["resource"]
        host = spec["host"]

        yield "Fetching HydroShare Resource {}.\n".format(resource_id)

        bag_url = "{}{}".format(host["django_irods"], resource_id)

        # bag downloads are prepared on demand and may need some time
        filehandle = self._urlopen(bag_url)

        zip_file_object = zipfile.ZipFile(filehandle, 'r')
        yield "Downloaded, unpacking contents.\n"
        zip_file_object.extractall("temp")
        # resources store the contents in the data/contents directory, which is all we want to keep
        contents_dir = os.path.join("temp", self.resource_id, "data", "contents")
        files = os.listdir(contents_dir)
        for f in files:
            shutil.move(os.path.join(contents_dir, f), output_dir)
        yield "Finished, cleaning up.\n"
        shutil.rmtree("temp")

    @property
    def content_id(self):
        """The HydroShare resource ID"""
        return self.resource_id
