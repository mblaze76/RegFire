import unittest
from unittest.mock import Mock, patch
from runtime_startup import prepare_store, prepare_owner

class RuntimeStartupTests(unittest.TestCase):
    def test_local_retains_migration_behavior(self):
        store=Mock()
        prepare_store(store,Mock(secure_cookies=False))
        store.initialize.assert_called_once_with()
        store.connect.assert_not_called()

    def test_production_does_not_migrate(self):
        from unittest.mock import MagicMock
        store=MagicMock(schema='synthetic_staging')
        prepare_store(store,Mock(secure_cookies=True))
        store.initialize.assert_not_called()
        calls=store.connect.return_value.__enter__.return_value.execute.call_args_list
        self.assertEqual(len(calls),8)
        for call in calls[:-1]:
            self.assertTrue(call.args[0].as_string().startswith('SELECT 1 FROM "synthetic_staging".'))

    def test_production_requires_existing_owner(self):
        access=Mock(); access.configured.return_value=False
        with patch('owner_setup.prepare') as bootstrap:
            with self.assertRaises(RuntimeError): prepare_owner(access,Mock(secure_cookies=True))
            bootstrap.assert_not_called()

    def test_production_existing_owner_does_not_create_token(self):
        access=Mock(); access.configured.return_value=True
        with patch('owner_setup.prepare') as bootstrap:
            prepare_owner(access,Mock(secure_cookies=True))
            bootstrap.assert_not_called()

    def test_local_retains_owner_setup(self):
        access=Mock()
        with patch('owner_setup.prepare') as bootstrap:
            prepare_owner(access,Mock(secure_cookies=False))
            bootstrap.assert_called_once_with(access)
