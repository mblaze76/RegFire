import json,unittest,os
from pathlib import Path
from unittest.mock import patch
class StagingSafetyTests(unittest.TestCase):
 def test_database_and_uploads_remain_private_and_retained(self):
  t=json.loads((Path(__file__).parents[1]/'deploy/staging.json').read_text())['Resources']
  db=t['Database'];self.assertFalse(db['Properties']['PubliclyAccessible']);self.assertTrue(db['Properties']['StorageEncrypted']);self.assertEqual(db['DeletionPolicy'],'Retain')
  self.assertTrue(t['Uploads']['Properties']['Encrypted']);self.assertEqual(t['Uploads']['DeletionPolicy'],'Retain')
  ingress=t['DataSecurity']['Properties']['SecurityGroupIngress']
  self.assertTrue(all('SourceSecurityGroupId' in rule and 'CidrIp' not in rule for rule in ingress))
 def test_service_starts_at_zero_without_bootstrap_and_uses_digest(self):
  t=json.loads((Path(__file__).parents[1]/'deploy/staging.json').read_text())
  self.assertEqual(t['Parameters']['DesiredCount']['Default'],0)
  self.assertIn('@sha256:',t['Parameters']['ImageDigest']['AllowedPattern'])
  self.assertTrue(t['Resources']['Service']['Properties']['DeploymentConfiguration']['DeploymentCircuitBreaker']['Rollback'])
 def test_runtime_cannot_read_master_secret(self):
  t=json.loads((Path(__file__).parents[1]/'deploy/staging.json').read_text())
  policy=t['Resources']['ExecutionRole']['Properties']['Policies'][0]['PolicyDocument']
  self.assertNotIn('MasterUserSecret',json.dumps(policy));self.assertNotIn('OwnerSecretArn',json.dumps(policy))
 def test_staging_blocks_payment_network_before_request(self):
  import payment_providers
  with patch.dict(os.environ,REGFIRE_STAGING='1'),patch.object(payment_providers,'urlopen') as network:
   with self.assertRaises(payment_providers.ProviderError):payment_providers.request('https://example.test')
   network.assert_not_called()
