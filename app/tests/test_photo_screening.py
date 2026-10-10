import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from photo_screening import screen, validate_settings, PhotoRejected, ScreeningUnavailable, public_status
from server import validate
from tests.test_events import PostgresTest, draft

POLICY = dict(enabled=True, safe_search=True, face_check=True, threshold='LIKELY')
GOOD = {'responses': [{'safeSearchAnnotation': dict(adult='VERY_UNLIKELY', violence='UNLIKELY', racy='UNLIKELY'), 'faceAnnotations': [{'detectionConfidence': 0.99}]}]}

class ScreeningTests(unittest.TestCase):
    def test_approved(self):
        self.assertEqual(screen(b'normalized image', POLICY, lambda _: GOOD)['status'], 'approved')

    def test_rejected_content_and_face(self):
        for category in ('adult', 'violence', 'racy'):
            response = copy.deepcopy(GOOD)
            response['responses'][0]['safeSearchAnnotation'][category] = 'LIKELY'
            with self.assertRaises(PhotoRejected):
                screen(b'image', POLICY, lambda _: response)
        for faces in ([], [{'detectionConfidence': 0.7}], [{'detectionConfidence': 0.99}]*2):
            response = copy.deepcopy(GOOD)
            response['responses'][0]['faceAnnotations'] = faces
            with self.assertRaises(PhotoRejected):
                screen(b'image', POLICY, lambda _: response)

    def test_missing_unknown_partial_and_provider_failure(self):
        responses = [{}, {'responses': []}, {'responses': [{'error': {'message': 'private provider detail'}}]}, {'responses': [{'faceAnnotations': []}]}]
        for response in responses:
            with self.assertRaises(ScreeningUnavailable):
                screen(b'image', POLICY, lambda _: response)
        with self.assertRaises(ScreeningUnavailable):
            screen(b'image', POLICY, lambda _: (_ for _ in ()).throw(ScreeningUnavailable('unavailable')))
        response = copy.deepcopy(GOOD)
        response['responses'][0]['safeSearchAnnotation']['adult'] = 'UNKNOWN'
        with self.assertRaises(ScreeningUnavailable):
            screen(b'image', POLICY, lambda _: response)

    def test_disabled_does_not_call_provider(self):
        with self.assertRaises(PhotoRejected):
            screen(b'image', dict(POLICY, enabled=False), lambda _: self.fail('Provider was called'))
        for value in ({'enabled': 'false'}, dict(POLICY, face_check=False), dict(POLICY, safe_search=False), dict(POLICY, threshold='UNKNOWN')):
            with self.assertRaises(ValueError):
                validate_settings(value)
        self.assertFalse(validate(draft())['photo_upload']['enabled'])

    def test_status_never_discloses_key_or_claims_live_verification(self):
        with patch.dict(os.environ, {'REGFIRE_GOOGLE_VISION_API_KEY': 'synthetic-key'}):
            result = public_status()
            self.assertTrue(result['configured'])
            self.assertNotIn('synthetic-key', str(result))
            self.assertFalse(result['live_verified'])
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'REGFIRE_GOOGLE_VISION_API_KEY': ''}), patch('photo_screening.KEY_FILE', Path(tmp)/'key'):
            self.assertEqual(public_status()['status'], 'unconfigured')
            path=Path(tmp)/'key';path.write_text('synthetic-key');path.chmod(0o644)
            self.assertEqual(public_status()['status'], 'error')

class PhotoSettingsTests(PostgresTest):
    def test_photo_policy_save_reload_and_event_isolation(self):
        from datetime import datetime, timezone
        import uuid
        one = self.store.save(str(uuid.uuid4()), validate(draft() | {'photo_upload': POLICY}), datetime.now(timezone.utc).isoformat(), False)
        two = self.store.save(str(uuid.uuid4()), validate(draft()), datetime.now(timezone.utc).isoformat(), False)
        rows = {row['id']: row for row in self.store.list()}
        self.assertTrue(rows[one['id']]['photo_upload']['enabled'])
        self.assertFalse(rows[two['id']]['photo_upload']['enabled'])
        child = next(flow['id'] for flow in self.store.flows(one['id'], {'name': 'Exhibitor', 'kind': 'exhibitor'}, datetime.now(timezone.utc).isoformat()) if flow['id'] != one['id'])
        self.store.save(one['id'], validate(draft() | {'photo_upload': dict(POLICY, enabled=False)}), datetime.now(timezone.utc).isoformat(), True)
        from psycopg import sql
        with self.store.connect() as conn:
            row = conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(self.store.table()), (child,)).fetchone()
        self.assertFalse(row[0]['photo_upload']['enabled'])
