"""
Tests for flocker base test cases.
"""

import errno
import shutil
import string

from hypothesis import assume, given
from hypothesis.strategies import binary, integers, lists, text
from testtools import TestCase
from testtools.matchers import (
    AllMatch,
    AfterPreprocessing,
    DirExists,
    HasLength,
    Equals,
    MatchesAny,
    LessThan,
    Not,
    PathExists,
    StartsWith,
)
from testtools.testresult.doubles import Python27TestResult
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from .._base import (
    AsyncTestCase,
    _path_for_test_id,
)


class AsyncTestCaseTests(TestCase):
    """
    Tests for `AsyncTestCase`.
    """

    @given(binary(average_size=30))
    def test_trial_skip_exception(self, reason):
        """
        If tests raise the ``SkipTest`` exported by Trial, then that's
        recorded as a skip.
        """

        class SkippingTest(AsyncTestCase):
            def test_skip(self):
                raise unittest.SkipTest(reason)

        test = SkippingTest('test_skip')
        # We need a test result double that we can useful results from, and
        # the Python 2.7 TestResult is the lowest common denominator.
        result = Python27TestResult()
        test.run(result)
        # testing-cabal/testtools c51fdb854 adds a public API for this. Update
        # to use new API when we start using a version later than 1.8.0.
        self.assertEqual([
            ('startTest', test),
            ('addSkip', test, reason),
            ('stopTest', test),
        ], result._events)

    def test_mktemp_doesnt_exist(self):
        """
        ``mktemp`` returns a path that doesn't exist inside a directory that
        does.
        """

        class SomeTest(AsyncTestCase):
            def test_pass(self):
                pass

        test = SomeTest('test_pass')
        temp_path = FilePath(test.mktemp())
        self.addCleanup(_remove_dir, temp_path.parent())

        self.expectThat(temp_path.parent().path, DirExists())
        self.assertThat(temp_path.path, Not(PathExists()))


identifier_characters = string.ascii_letters + string.digits + '_'
identifiers = text(average_size=20, min_size=1, alphabet=identifier_characters)
fqpns = lists(
    identifiers, min_size=1, average_size=5).map(lambda xs: '.'.join(xs))


class MakeTemporaryTests(TestCase):
    """
    Tests for code for making temporary files and directories for tests.
    """

    @given(test_id=fqpns, max_length=integers(min_value=1, max_value=64))
    def test_directory_for_test(self, test_id, max_length):
        """
        _path_for_test_id returns a relative path of $module/$class/$method for
        the given test id.
        """
        assume(test_id.count('.') > 1)
        path = _path_for_test_id(test_id, max_length)
        self.expectThat(path, Not(StartsWith('/')))
        segments = path.split('/')
        self.expectThat(segments, HasLength(3))
        self.assertThat(
            segments,
            AllMatch(
                AfterPreprocessing(
                    len, MatchesAny(
                        LessThan(max_length),
                        Equals(max_length)
                    )
                )
            )
        )

    @given(test_id=fqpns)
    def test_too_short_test_id(self, test_id):
        """
        If the given test id is has too few segments, raise an error.
        """
        assume(test_id.count('.') < 2)
        self.assertRaises(ValueError, _path_for_test_id, test_id)


def _remove_dir(path):
    """
    Safely remove the directory 'path'.
    """
    try:
        shutil.rmtree(path.path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
