import base64
import hashlib


class AssetFingerprinter(object):
    """
    Get a unique hash for an asset file, so that it doesn't stay cached
    when it changes

    Usage:

        in the application
        template_data.asset_fingerprinter = AssetFingerprinter()

        where template data is how you pass variables to every template.

        in template.html:
        {{ asset_fingerprinter.get_url('stylesheets/application.css') }}

    * 'app/static' is assumed to be the root for all asset files
    """

    def __init__(self, asset_root="/static/", filesystem_path="app/static/", cdn_domain=None):
        self._cache = {}
        self._sri_cache = {}
        self._cdn_domain = cdn_domain
        self._asset_root = asset_root
        self._filesystem_path = filesystem_path

    def get_url(self, asset_path):
        if asset_path not in self._cache:
            self._cache[asset_path] = (
                self._asset_root + asset_path + "?" + self.get_asset_fingerprint(self._filesystem_path + asset_path)
            )
        return self._cache[asset_path]

    def get_sri(self, asset_path):
        if asset_path not in self._sri_cache:
            self._sri_cache[asset_path] = self.get_asset_sri(self._filesystem_path + asset_path)
        return self._sri_cache[asset_path]

    def get_s3_url(self, asset_path):
        if asset_path not in self._cache:
            self._cache[asset_path] = f"https://{self._cdn_domain}/static/{asset_path}"
        return self._cache[asset_path]

    def get_asset_fingerprint(self, asset_file_path):
        return hashlib.md5(self.get_asset_file_contents(asset_file_path)).hexdigest()

    def get_asset_sri(self, asset_file_path):
        hash = hashlib.sha256(self.get_asset_file_contents(asset_file_path)).digest()
        hash_base64 = base64.b64encode(hash).decode()
        return "sha256-{}".format(hash_base64)

    def get_asset_file_contents(self, asset_file_path):
        with open(asset_file_path, "rb") as asset_file:
            contents = asset_file.read()
        return contents

    def is_static_asset(self, url):
        return url and url.startswith(self._asset_root)


asset_fingerprinter = AssetFingerprinter()
