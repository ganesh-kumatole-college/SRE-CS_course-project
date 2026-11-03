import unittest

import misdet


class PackageScaffoldTests(unittest.TestCase):
    def test_package_declares_version(self) -> None:
        self.assertEqual(misdet.__version__, "0.1.0")
