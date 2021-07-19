import collections
import tempfile
import pathlib
import unittest
import zipfile

from ..checksum_validator import (
    validate_checksums, md5sum_directory, md5sum, from_checksum_format,
)
from .test_parse import TEST_DATA


class ValidateChecksumTests(unittest.TestCase):
    """
    Tests adapted from `/qiime2/core/archive/tests/test_archiver.py`
    """
    def test_checksums_match(self):
        """
        Test a collection of intact archives from v0 to v5
        """
        for archv_vrsn in TEST_DATA:
            fp = TEST_DATA[archv_vrsn]['qzv_fp']
            with zipfile.ZipFile(fp) as zf:
                diff = validate_checksums(zf)

                self.assertEqual(diff.added, {})
                self.assertEqual(diff.removed, {})
                self.assertEqual(diff.changed, {})

    def test_checksums_mismatch(self):
        """
        Mangle an intact v5 Archive and confirm we catch the changes
        """
        with tempfile.TemporaryDirectory() as tmpd:
            # Deleting files from zip archives is hard, so we'll
            # Make a temporary copy of our archive without a 'VERSION' file
            # adapted from https://stackoverflow.com/a/513889/9872253
            tmp_arc = pathlib.Path(tmpd) / 'mangled.qzv'
            fp_pfx = pathlib.Path(TEST_DATA['5']['uuid'])
            zin = zipfile.ZipFile(TEST_DATA['5']['qzv_fp'], 'r')
            zout = zipfile.ZipFile(str(tmp_arc), 'w')
            for item in zin.infolist():
                buffer = zin.read(item.filename)
                # Original tests use VERSION. Here, that raises a confounding
                # error, so we're switching to `metadata.yaml`
                vzn_filename = str(fp_pfx / 'metadata.yaml')
                if (item.filename != vzn_filename):
                    zout.writestr(item, buffer)
            zout.close()
            zin.close()

            diff = None

            with zipfile.ZipFile(tmp_arc, 'a') as zf:
                # We'll also dd a new file
                new_fn = str(fp_pfx / 'tamper.txt')
                zf.writestr(new_fn, 'extra file')

                # and overwrite an existing file with junk
                extant_fn = str(fp_pfx / 'data' / 'index.html')
                # we expect a warning that we're overwriting the filename
                # this cm stops the warning from propagating up stderr/out
                with self.assertWarnsRegex(UserWarning, 'Duplicate name'):
                    with zf.open(extant_fn, 'w') as myfile:
                        myfile.write(b'999\n')

                diff = validate_checksums(zf)

            # Here we'll just check name for reasons of simplicity
            self.assertEqual(list(diff.removed.keys()), ['metadata.yaml'])
            self.assertEqual(
                diff.added,
                {'tamper.txt': '296583001b00d2b811b5871b19e0ad28'})
            self.assertEqual(
                diff.changed,
                {'data/index.html': ('065031e17943cd0780f197874c4f011e',
                                     'f47bc36040d5c7db08e4b3a457dcfbb2')
                 })


class MD5SumDirectoryTests(unittest.TestCase):
    """
    Are the filename/checksum pairs we calculate from an archive correct?

    These tests (like our md5sum_directory() implementation assume
    that all QIIME 2 Archives contain a root dir named with the terminal
    uuid. (This is true, and likely always will be.)

    Tests adapted from qiime2/core/tests/test_util.py
    All expected results were generated via GNU coreutils md5sum
    """
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory(prefix='qiime2-test-temp-')
        self.test_path = pathlib.Path(self.test_dir.name)
        self.zip_fname = str(self.test_path / 'file.zip')
        self.toy_uuid = pathlib.Path('<some_uuid>')

    def tearDown(self):
        self.test_dir.cleanup()

    def make_zip_archive(self, bytes_, relpath):
        path = self.test_path / relpath
        with path.open(mode='wb') as fh:
            fh.write(bytes_)

        with zipfile.ZipFile(self.zip_fname, 'a') as zf:
            # Insert toy_uuid to mimic the root_uuid assumption of an Archive
            zf.write(str(path), self.toy_uuid / relpath)

    def test_single_file(self):
        self.make_zip_archive(b'Normal text\nand things\n', 'foobarbaz.txt')
        with zipfile.ZipFile(self.zip_fname) as zf:
            self.assertEqual(
                md5sum_directory(zf), {'foobarbaz.txt':
                                       '93b048d0202e4b06b658f3aef1e764d3'})

    def test_single_file_nested(self):
        nested_dir = self.test_path / 'bar'
        nested_dir.mkdir()

        filepath = (nested_dir / 'foo.baz').relative_to(self.test_path)
        self.make_zip_archive(b'anything at all', filepath)

        with zipfile.ZipFile(self.zip_fname) as zf:
            self.assertEqual(md5sum_directory(zf),
                             {'bar/foo.baz':
                             'dcc0975b66728be0315abae5968379cb'})

    def test_buncha_stuff(self):
        nested_dir = self.test_path / 'beta'
        nested_dir.mkdir()
        filepath = (nested_dir / '10').relative_to(self.test_path)
        self.make_zip_archive(b'10', filepath)
        filepath = (nested_dir / '1').relative_to(self.test_path)
        self.make_zip_archive(b'1', filepath)
        filepath = (nested_dir / '2').relative_to(self.test_path)
        self.make_zip_archive(b'2', filepath)

        nested_dir = self.test_path / 'alpha'
        nested_dir.mkdir()
        filepath = (nested_dir / 'foo').relative_to(self.test_path)
        self.make_zip_archive(b'foo', filepath)
        filepath = (nested_dir / 'bar').relative_to(self.test_path)
        self.make_zip_archive(b'bar', filepath)

        self.make_zip_archive(b'z', 'z')

        with zipfile.ZipFile(self.zip_fname) as zf:
            self.assertEqual(
                md5sum_directory(zf),
                dict([
                    ('z', 'fbade9e36a3f36d3d676c1b808451dd7'),
                    ('alpha/bar', '37b51d194a7513e45b56f6524f2d51f2'),
                    ('alpha/foo', 'acbd18db4cc2f85cedef654fccc4a4d8'),
                    ('beta/1', 'c4ca4238a0b923820dcc509a6f75849b'),
                    ('beta/10', 'd3d9446802a44259755d38e6d163e820'),
                    ('beta/2', 'c81e728d9d4c2f636f067f89cc14862c'),
                ]))

    def test_can_use_string(self):
        nested_dir = self.test_path / 'bar'
        nested_dir.mkdir()

        filepath = (nested_dir / 'foo.baz').relative_to(self.test_path)
        self.make_zip_archive(b'anything at all', filepath)

        with zipfile.ZipFile(self.zip_fname) as zf:
            self.assertEqual(
                md5sum_directory(zf),
                collections.OrderedDict([
                    ('bar/foo.baz', 'dcc0975b66728be0315abae5968379cb')
                ]))


class MD5SumTests(unittest.TestCase):
    # Tests adapted from qiime2/core/tests/test_util.py
    # All expected results were generated via GNU coreutils md5sum
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory(prefix='qiime2-test-temp-')
        self.test_path = pathlib.Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def make_zip_archive(self, bytes_):
        # Make a file with bytes_ for contents and then zip it up
        arcname = 'file'
        path = self.test_path / arcname
        with path.open(mode='wb') as fh:
            fh.write(bytes_)

        zipname = 'file.zip'
        zfpath = str(self.test_path / zipname)

        with zipfile.ZipFile(zfpath, 'w') as zf:
            zf.write(str(path), arcname)

        return zfpath, arcname

    def test_empty_file(self):
        zfpath, arcname = self.make_zip_archive(b'')
        with zipfile.ZipFile(zfpath) as zf:
            self.assertEqual(md5sum(zf, arcname),
                             'd41d8cd98f00b204e9800998ecf8427e')

    def test_single_byte_file(self):
        zfpath, arcname = self.make_zip_archive(b'a')
        with zipfile.ZipFile(zfpath) as zf:
            self.assertEqual(md5sum(zf, arcname),
                             '0cc175b9c0f1b6a831c399e269772661')

    def test_large_file(self):
        zfpath, arcname = self.make_zip_archive(b'verybigfile' * (1024 * 50))
        with zipfile.ZipFile(zfpath) as zf:
            self.assertEqual(md5sum(zf, arcname),
                             '27d64211ee283283ad866c18afa26611')

    def test_can_use_string(self):
        zfpath, arcname = self.make_zip_archive(b'Normal text\nand things\n')
        with zipfile.ZipFile(zfpath) as zf:
            self.assertEqual(md5sum(zf, arcname),
                             '93b048d0202e4b06b658f3aef1e764d3')


class FromChecksumFormatTests(unittest.TestCase):
    # Tests adapted from qiime2/core/tests/test_util.py

    def test_from_simple(self):
        fp, chks = from_checksum_format(
            b'd9724aeba59d8cea5265f698b2c19684  this/is/a/filepath')
        self.assertEqual(fp, 'this/is/a/filepath')
        self.assertEqual(chks, 'd9724aeba59d8cea5265f698b2c19684')

    def test_from_hard(self):
        line = (
            rb'\939aaaae6098ebdab049b0f3abe7b68c  filepath/\n/with/\\newline' +
            b'\n'  # ewline from a checksum "file"
        )
        print(type(line))
        fp, chks = from_checksum_format(line)

        self.assertEqual(fp, 'filepath/\n/with/\\newline')
        self.assertEqual(chks, '939aaaae6098ebdab049b0f3abe7b68c')

    def test_from_legacy_format(self):
        fp, chks = from_checksum_format(
            rb'0ed29022ace300b4d96847882daaf0ef *this/means/binary/mode')

        self.assertEqual(fp, 'this/means/binary/mode')
        self.assertEqual(chks, '0ed29022ace300b4d96847882daaf0ef')