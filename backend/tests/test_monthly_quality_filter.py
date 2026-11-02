import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class MonthlyQualityFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the original read-only router under a private package name.
        # Inject its existing authentication dependency only during this import.
        auth = types.ModuleType('app.core.auth')
        auth.get_current_user = lambda: types.SimpleNamespace(role='HQ_SAFE')
        previous = sys.modules.get('app.core.auth')
        sys.modules['app.core.auth'] = auth
        root = Path(__file__).resolve().parents[1] / 'app/modules/monthly_collection'
        package = types.ModuleType('monthly_quality_filter_test')
        package.__path__ = [str(root)]
        sys.modules[package.__name__] = package
        try:
            spec = importlib.util.spec_from_file_location(package.__name__+'.routes', root/'routes.py')
            cls.routes = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.routes
            spec.loader.exec_module(cls.routes)
        finally:
            if previous is None:
                sys.modules.pop('app.core.auth', None)
            else:
                sys.modules['app.core.auth'] = previous
        cls.auth = staticmethod(auth.get_current_user)

    def setUp(self):
        self.parent = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=self.parent)
        self.root = Path(self.temp.name)
        self.assertTrue(self.root.resolve().is_relative_to(self.parent))
        self.routes.ROOT = self.root
        self.app = FastAPI()
        self.app.include_router(self.routes.router)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.assertTrue(self.root.resolve().is_relative_to(self.parent))
        self.temp.cleanup()

    def snapshot(self, flagged, total=450):
        rows = []
        notes = []
        for n in range(total):
            ident = f'{n:064x}'
            digest = hashlib.sha256(str(n).encode()).hexdigest()
            row = dict(id=ident, sha256=digest, size=10, category='risk', month='2026-11',
                       team='1팀', site='연결현장' if n%2==0 else '', site_code='99999' if n%2==0 else '',
                       filename=f'자료{n}.pdf', state='SAVED' if n%2==0 else 'SITE_REVIEW',
                       first_seen='2026-11-01T00:00:00+09:00', last_seen='2026-11-01T00:00:00+09:00')
            rows.append(row)
            if n in flagged:
                notes.append(dict(id=ident, sha256=digest, kind='INVALID_DATE', document_month='2026-11', day=31))
        value = dict(schema=1, generated_at='2026-11-03T03:00:00+09:00', collection_state='NAS_SAVED',
                     review_count=121, items=rows, reviewed_source_notes=notes)
        (self.root/'current.json').write_text(json.dumps(value, ensure_ascii=False), 'utf8')
        return value

    def test_filter_runs_before_first_page_limit(self):
        self.snapshot({1, 2})
        ordinary = self.client.get('/monthly-collection/overview').json()
        self.assertEqual(len(ordinary['items']), 200)
        self.assertFalse({f'{1:064x}', f'{2:064x}'} & {x['id'] for x in ordinary['items']})
        response = self.client.get('/monthly-collection/overview?quality=review')
        value = response.json()
        self.assertEqual(value['count'], 2)
        self.assertEqual({x['id'] for x in value['items']}, {f'{1:064x}', f'{2:064x}'})
        self.assertEqual(value['quality_counts'], {'all':450, 'review':2})
        self.assertEqual(value['quality_filter'], 'review')
        self.assertIsNone(value['next_offset'])

    def test_more_than_one_page_keeps_complete_stable_set(self):
        self.snapshot(set(range(260)))
        first = self.client.get('/monthly-collection/overview?quality=review').json()
        second = self.client.get('/monthly-collection/overview?quality=review&offset=200').json()
        self.assertEqual(first['count'], 260)
        self.assertEqual(first['next_offset'], 200)
        self.assertIsNone(second['next_offset'])
        self.assertEqual(len(first['items']), 200)
        self.assertEqual(len(second['items']), 60)
        self.assertEqual({x['id'] for x in first['items']+second['items']}, {f'{n:064x}' for n in range(260)})

    def test_existing_month_site_and_text_filters_are_retained(self):
        self.snapshot({1, 2})
        value = self.client.get('/monthly-collection/overview?quality=review&binding=linked&q=연결현장&month=2026-11').json()
        self.assertEqual(value['count'], 1)
        self.assertEqual(value['items'][0]['id'], f'{2:064x}')
        self.assertEqual(value['quality_counts'], {'all':225, 'review':1})
        self.assertEqual(value['review_count'], 121)
        self.assertEqual(self.client.get('/monthly-collection/overview?quality=review&month=2026-10').json()['count'], 0)

    def test_clear_filter_restores_full_set_without_writing_source(self):
        original = self.snapshot({1, 2})
        raw = (self.root/'current.json').read_bytes()
        self.client.get('/monthly-collection/overview?quality=review')
        value = self.client.get('/monthly-collection/overview').json()
        self.assertEqual(value['count'], 450)
        self.assertEqual(value['linked_file_count']+value['pending_file_count'], 450)
        self.assertEqual(value['quality_filter'], '')
        self.assertEqual((self.root/'current.json').read_bytes(), raw)
        self.assertEqual(json.loads(raw), original)

    def test_valid_zero_is_separate_from_failed_read(self):
        self.snapshot(set())
        value = self.client.get('/monthly-collection/overview?quality=review').json()
        self.assertEqual(value['count'], 0)
        self.assertEqual(value['state'], 'NAS_SAVED')
        self.assertEqual(value['quality_counts'], {'all':450, 'review':0})
        (self.root/'current.json').write_text('bad', 'utf8')
        self.assertEqual(self.client.get('/monthly-collection/overview?quality=review').status_code, 503)

    def test_permissions_contract_and_private_fields_do_not_expand(self):
        self.snapshot({1, 2})
        for role in ['SITE','HQ_OTHER']:
            self.app.dependency_overrides[self.auth] = lambda role=role: types.SimpleNamespace(role=role)
            self.assertEqual(self.client.get('/monthly-collection/overview?quality=review').status_code, 403)
        self.app.dependency_overrides.clear()
        response = self.client.get('/monthly-collection/overview?quality=review')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn('sha256', response.json()['items'][0])
        self.assertNotIn('site_code', response.json()['items'][0])
        self.assertEqual(self.client.get('/monthly-collection/overview?quality=unknown').status_code, 422)
        self.assertEqual(self.client.post('/monthly-collection/overview', json={}).status_code, 405)


if __name__ == '__main__':
    unittest.main()
