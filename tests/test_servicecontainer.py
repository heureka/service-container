import unittest
from unittest.mock import Mock

from servicecontainer import ServiceContainer


class ServiceContainerTest(unittest.TestCase):
    def test_lazy_call(self):
        foo_service = Mock(return_value="foo_service")

        sc = ServiceContainer(
            foo=lambda: foo_service(),
        )
        foo_service.assert_not_called()

        self.assertEqual(sc.foo, "foo_service")
        foo_service.assert_called_once_with()

    def test_consistent_dependencies_for_subservices(self):
        sc = ServiceContainer(
            obj=lambda: object(),
            foo=lambda t: t.obj,
            bar=lambda t: t.obj,
            comparison=lambda t: t.foo is t.bar,
        )

        self.assertTrue(sc.comparison)

    def test_transaction(self):
        sc = ServiceContainer(
            obj=lambda: object(),
            subobj=lambda t: t.obj
        )

        self.assertIsNot(sc.obj, sc.obj)
        self.assertIsNot(sc.subobj, sc.subobj)

        with sc as transaction:
            self.assertIs(transaction.obj, transaction.obj)
            self.assertIs(transaction.subobj, transaction.subobj)

    def test_circular_dependency(self):
        sc = ServiceContainer(
            foo=lambda t: t.bar,
            bar=lambda t: t.foo
        )

        # RecursionError is not defined in Python < 3.5
        self.assertRaisesRegex(RuntimeError, "recursion", lambda: sc.foo)

    def test_exception_in_provider(self):
        def throw(cls, str):
            raise cls(str)

        sc = ServiceContainer(
            foo=lambda t: throw(IOError, "Nope")
        )

        self.assertRaisesRegex(IOError, "Nope", lambda: sc.foo)

    def test_exception_in_transaction(self):
        def fail():
            sc = ServiceContainer(
                foo=lambda: object()
            )

            with sc as sct:
                return sct.foo.everybody_do_the_flop()

        self.assertRaisesRegex(AttributeError, "everybody_do_the_flop", fail)

    def test_params(self):
        foo_service = Mock(return_value="foo_service")
        bar_service = Mock(return_value="bar_service")

        sc = ServiceContainer(
            foo=lambda t: foo_service(t.params["lang"]),
            bar=lambda t: bar_service(t.params["lang"], t.params["env"])
        )

        # fails for missing param
        self.assertRaises(KeyError, lambda: sc.foo)

        with sc(lang="cz") as sct:
            # test use of param, caching works
            self.assertEqual(sct.foo, "foo_service")
            self.assertEqual(sct.foo, "foo_service")
            foo_service.assert_called_once_with('cz')

            # param cannot be overridden
            def fail():
                with sct(lang="sk") as sct_sk:
                    self.fail("Already set param cannot be overridden.")

            self.assertRaisesRegex(ValueError, "Cannot override", fail)

            # but new param can be added
            with sct(env="test") as sct_env:
                self.assertEqual(sct_env.bar, "bar_service")

                bar_service.assert_called_once_with("cz", "test")
