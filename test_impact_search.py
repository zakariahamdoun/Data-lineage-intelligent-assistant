"""Impact-only DSL retrieval: no live Atlas required."""
import unittest
from unittest.mock import Mock
from test_lineage_routing import load_functions


class ImpactSearchTests(unittest.TestCase):
    def test_active_unique_guids_and_pagination(self):
        for kind in ('PostgreSQLTable', 'SQLiteTable', 'PostgreSQLColumn', 'SQLiteColumn'):
            with self.subTest(kind=kind):
                n = load_functions()
                first = [{'guid': str(i), 'status': 'ACTIVE'} for i in range(998)]
                first += [{'guid': 'deleted', 'status': 'DELETED'}, first[0]]
                fetch = Mock(side_effect=[{'entities': first}, {'entities': [
                    first[0], {'guid': 'last', 'status': 'ACTIVE'},
                    {'guid': 'purged', 'status': 'PURGED'}]}])
                n['atlas_get'] = fetch
                result = n['search_type_advanced'](kind)
                self.assertEqual(len(result), 999)
                self.assertEqual(len({e['guid'] for e in result}), 999)
                for call, offset in zip(fetch.call_args_list, (0, 1000)):
                    self.assertEqual(call.args, ('/api/atlas/v2/search/dsl', {
                        'query': 'from ' + kind, 'limit': 1000, 'offset': offset}))

    def test_empty_and_failure_do_not_fallback_to_basic(self):
        n = load_functions()
        n['atlas_get'] = Mock(return_value={'entities': []})
        self.assertEqual(n['search_type_advanced']('SQLiteTable'), [])
        n['atlas_get'] = Mock(side_effect=RuntimeError('Atlas unavailable'))
        with self.assertRaisesRegex(RuntimeError, 'Atlas unavailable'):
            n['search_type_advanced']('PostgreSQLTable')
        self.assertEqual(n['atlas_get'].call_count, 1)

    def test_impact_catalog_uses_only_dsl_and_default_stays_basic(self):
        n = load_functions()
        n['search_type_advanced'] = Mock(return_value=[])
        n['search_type'] = Mock(return_value=[])
        n['pg_catalog'](use_dsl=True)
        n['search_type'].assert_not_called()
        self.assertEqual({c.args[0] for c in n['search_type_advanced'].call_args_list},
                         {'PostgreSQLTable', 'PostgreSQLColumn', 'PostgreSQLDatabase', 'Process'})
        n['search_type_advanced'].reset_mock()
        catalog = n['pg_catalog']()
        n['search_type_advanced'].assert_not_called()
        n['pg_catalog'] = Mock(side_effect=AssertionError('Unexpected catalog reload'))
        n['downstream_table'] = Mock(return_value={})
        result = n['impact_pg']('unused', 'Table', catalog=catalog)
        self.assertEqual(result['tables'], [])
        n['pg_catalog'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
