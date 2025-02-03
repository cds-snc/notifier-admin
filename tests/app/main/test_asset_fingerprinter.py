# coding=utf-8

from app.asset_fingerprinter import AssetFingerprinter


class TestAssetFingerprint(object):
    def test_url_format(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode("utf-8")
        asset_fingerprinter = AssetFingerprinter(asset_root="/suppliers/static/")
        assert (
            asset_fingerprinter.get_url("application.css") == "/suppliers/static/application.css?418e6f4a6cdf1142e45c072ed3e1c90a"  # noqa
        )
        assert (
            asset_fingerprinter.get_url("application-ie6.css")
            == "/suppliers/static/application-ie6.css?418e6f4a6cdf1142e45c072ed3e1c90a"  # noqa
        )

    def test_building_file_path(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            document.write('Hello world!');
        """.encode("utf-8")
        fingerprinter = AssetFingerprinter()
        fingerprinter.get_url("javascripts/application.js")
        fingerprinter.get_asset_file_contents.assert_called_with("app/static/javascripts/application.js")

    def test_hashes_are_consistent(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode("utf-8")
        asset_fingerprinter = AssetFingerprinter()
        assert asset_fingerprinter.get_asset_fingerprint("application.css") == asset_fingerprinter.get_asset_fingerprint(
            "same_contents.css"
        )

    def test_hashes_are_different_for_different_files(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        asset_fingerprinter = AssetFingerprinter()
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode("utf-8")
        css_hash = asset_fingerprinter.get_asset_fingerprint("application.css")
        get_file_content_mock.return_value = """
            document.write('Hello world!');
        """.encode("utf-8")
        js_hash = asset_fingerprinter.get_asset_fingerprint("application.js")
        assert js_hash != css_hash

    def test_hash_gets_cached(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode("utf-8")
        fingerprinter = AssetFingerprinter()
        assert fingerprinter.get_url("application.css") == "/static/application.css?418e6f4a6cdf1142e45c072ed3e1c90a"
        fingerprinter._cache["application.css"] = "a1a1a1"
        assert fingerprinter.get_url("application.css") == "a1a1a1"
        fingerprinter.get_asset_file_contents.assert_called_once_with("app/static/application.css")

    def test_s3_url(self):
        fingerprinter = AssetFingerprinter(cdn_domain="assets.example.com")

        assert fingerprinter.get_s3_url("foo.png") == "https://assets.example.com/static/foo.png"

    def test_is_static_asset(self):
        fingerprinter = AssetFingerprinter(
            asset_root="https://example.com/static/",
            cdn_domain="assets.example.com",
        )

        assert fingerprinter.is_static_asset("https://example.com/static/image.png")
        assert not fingerprinter.is_static_asset("https://assets.example.com/image.png")
        assert not fingerprinter.is_static_asset("https://example.com/robots.txt")

    def test_sris_are_consistent(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode(
            "utf-8"
        )
        asset_fingerprinter = AssetFingerprinter()
        assert asset_fingerprinter.get_asset_sri("application.css") == asset_fingerprinter.get_asset_sri("same_contents.css")

    def test_sris_are_different_for_different_files(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        asset_fingerprinter = AssetFingerprinter()
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode(
            "utf-8"
        )
        css_hash = asset_fingerprinter.get_asset_sri("application.css")
        get_file_content_mock.return_value = """
            document.write('Hello world!');
        """.encode(
            "utf-8"
        )
        js_hash = asset_fingerprinter.get_asset_sri("application.js")
        assert js_hash != css_hash

    def test_sri_gets_cached(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = """
            body {
                font-family: nta;
            }
        """.encode(
            "utf-8"
        )
        fingerprinter = AssetFingerprinter()
        assert fingerprinter.get_sri("application.css") == "sha256-m6bbawn+w6J+skW4rZ8bVBUodfZDxY30ZY84rGICL3Q="
        fingerprinter._sri_cache["application.css"] = "a1a1a1"
        assert fingerprinter.get_sri("application.css") == "a1a1a1"
        fingerprinter.get_asset_file_contents.assert_called_once_with("app/static/application.css")


class TestAssetFingerprintWithUnicode(object):
    def test_can_read_self(self):
        "Ralph’s apostrophe is a string containing a unicode character"
        AssetFingerprinter(filesystem_path="tests/app/main/").get_url("test_asset_fingerprinter.py")
