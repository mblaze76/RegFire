import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from registration import starter,validate_page,pricing_preview,local_instant,applicable_rate


def rate(id,price,start='',end=''):
    return dict(id=id,name=id,price_minor=price,start=start,end=end)

def page(rates=None,fallback=False):
    data=starter(dict(id='sample',name='Sample'))
    data['regtypes'][0].update(price_minor=25000,use_default=fallback,rates=rates or [])
    return data

class RateTests(unittest.TestCase):
    def preview(self,data,at):return pricing_preview(data,'America/New_York',at)['regtypes']['attendee']
    def test_legacy_default_is_backward_compatible(self):
        data=starter(dict(id='sample',name='Sample'));data['regtypes'][0]['price_minor']=12345
        normalized=validate_page(data)
        self.assertTrue(normalized['regtypes'][0]['use_default']);self.assertEqual(normalized['regtypes'][0]['rates'],[])
        result=self.preview(data,'2026-10-01T12:00');self.assertEqual((result['status'],result['price_minor']),('default',12345))
    def test_exact_adjacent_boundaries(self):
        data=page([rate('early',10001,'2026-10-01T09:00','2026-10-02T09:00'),rate('standard',20002,'2026-10-02T09:00','2026-10-03T09:00')])
        self.assertEqual(self.preview(data,'2026-10-01T08:59')['status'],'unavailable')
        self.assertEqual(self.preview(data,'2026-10-01T09:00')['price_minor'],10001)
        self.assertEqual(self.preview(data,'2026-10-02T08:59')['name'],'early')
        self.assertEqual(self.preview(data,'2026-10-02T09:00')['price_minor'],20002)
        self.assertEqual(self.preview(data,'2026-10-03T09:00')['status'],'unavailable')
    def test_gap_expiry_and_explicit_fallback(self):
        data=page([rate('early',100,'2026-10-01T09:00','2026-10-02T09:00'),rate('late',300,'2026-10-04T09:00','2026-10-05T09:00')])
        for at in ('2026-09-30T09:00','2026-10-03T09:00','2026-10-06T09:00'):
            self.assertIsNone(self.preview(data,at)['price_minor'])
        data['regtypes'][0]['use_default']=True
        expired=self.preview(data,'2026-10-06T09:00')
        self.assertEqual((expired['status'],expired['price_minor']),('default',25000))
    def test_overlap_reversal_and_open_windows(self):
        invalid=[
            [rate('a',1,'2026-10-01T09:00','2026-10-03T09:00'),rate('b',2,'2026-10-02T09:00','2026-10-04T09:00')],
            [rate('a',1,'2026-10-03T09:00','2026-10-03T09:00')],
            [rate('a',1,'2026-10-04T09:00','2026-10-03T09:00')],
            [rate('a',1)],
            [rate('a',1,'','2026-10-03T09:00'),rate('b',2,'2026-10-02T09:00','')],
        ]
        for rates in invalid:
            with self.subTest(rates=rates),self.assertRaises(ValueError):validate_page(page(rates),'America/New_York')
        data=page([rate('before',100,'','2026-10-02T09:00'),rate('after',200,'2026-10-02T09:00','')])
        self.assertEqual(self.preview(data,'2020-01-01T00:00')['name'],'before')
        self.assertEqual(self.preview(data,'2030-01-01T00:00')['name'],'after')
    def test_timezone_and_dst(self):
        instant=local_instant('2026-10-01T09:00','America/New_York','start')
        self.assertEqual(instant,datetime(2026,10,1,13,tzinfo=timezone.utc))
        data=validate_page(page([rate('early',1,'2026-10-01T09:00','2026-10-01T10:00')]),'America/New_York')['regtypes'][0]
        self.assertEqual(applicable_rate(data,datetime(2026,10,1,12,59,tzinfo=timezone.utc),'America/New_York')['status'],'unavailable')
        self.assertEqual(applicable_rate(data,instant,'America/New_York')['status'],'scheduled')
        with self.assertRaises(ValueError):local_instant('2026-03-08T02:30','America/New_York','start')
        self.assertEqual(local_instant('2026-11-01T01:30','America/New_York','start'),datetime(2026,11,1,5,30,tzinfo=timezone.utc))
        with self.assertRaises(ValueError):validate_page(page([rate('dst',1,'2026-03-08T02:30','2026-03-08T04:00')]),'America/New_York')
    def test_invalid_period_prices_and_preview_time(self):
        for value in (1.5,True,-1,100000000):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_page(page([rate('a',value,'2026-01-01T00:00','')]))
        with self.assertRaises(ValueError):self.preview(page(),'not-a-time')
