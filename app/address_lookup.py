"""Optional address suggestions. No external calls until explicitly configured."""
import os,json,http.client,time,threading
from urllib.parse import urlencode
from membership import public_addresses,PinnedHTTPS,Unavailable
_last_call=0;_lock=threading.Lock()
COMPONENTS=('line1','line2','city','region','postal','country')

def config():
    provider=os.environ.get('REGFIRE_ADDRESS_PROVIDER','')
    from google_addresses import key
    if provider=='google' and key():return dict(configured=True,provider='Google Maps',fixture=False,message='Address text is sent to Google Maps for suggestions. This does not validate postal deliverability.')
    ready=provider=='geoapify' and bool(os.environ.get('REGFIRE_GEOAPIFY_API_KEY'))
    return dict(configured=ready or provider=='fixture',provider='Synthetic fixture' if provider=='fixture' else 'Geoapify' if ready else None,fixture=provider=='fixture',message='Synthetic suggestions only; no external lookup.' if provider=='fixture' else 'Address text is sent to Geoapify for suggestions. You can always enter an address manually.' if ready else 'Address suggestions are not configured. Enter the address manually.')

def normalize(data):
    if not isinstance(data,dict) or not isinstance(data.get('results'),list):raise Unavailable('Invalid address response.')
    result=[]
    for row in data['results'][:5]:
        if not isinstance(row,dict):continue
        def text(k):v=row.get(k,'');return v.strip()[:500] if isinstance(v,str) else ''
        street=text('address_line1') or ' '.join(filter(None,[text('housenumber'),text('street')]))
        item=dict(line1=street,city=text('city') or text('town') or text('village'),region=text('state'),postal=text('postcode'),country=text('country'),formatted=text('formatted'))
        if not item['formatted']:item['formatted']=', '.join(v for v in [street,item['city'],item['region'],item['postal'],item['country']] if v)
        if item['formatted']:result.append(item)
    return result

def transport(query,key):
    host='api.geoapify.com';conn=PinnedHTTPS(host,public_addresses(host)[0]);path='/v1/geocode/autocomplete?'+urlencode(dict(text=query,format='json',limit=5,apiKey=key))
    try:
        conn.request('GET',path,headers={'Accept':'application/json'});r=conn.getresponse()
        if r.status!=200:raise Unavailable('Address provider unavailable.')
        body=b'';deadline=time.monotonic()+10
        while len(body)<=131072:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise Unavailable('Address lookup timed out.')
            if conn.sock:conn.sock.settimeout(min(5,remaining))
            chunk=r.read1(min(8192,131073-len(body)))
            if not chunk:break
            body+=chunk
        if len(body)>131072:raise Unavailable('Address response too large.')
        return json.loads(body)
    except (OSError,ValueError,http.client.HTTPException):raise Unavailable('Address provider unavailable.')
    finally:conn.close()

def suggestions(query,fetch=transport,session=None):
    global _last_call
    if not isinstance(query,str) or not 3<=len(query.strip())<=300 or any(ord(c)<32 for c in query):raise ValueError('Enter 3–300 characters to search for an address.')
    state=config()
    if not state['configured']:return dict(status='unconfigured',suggestions=[],message=state['message'])
    if state['fixture']:
        rows=normalize({'results':[dict(address_line1='123 Example Street',city='Sample City',state='New York',postcode='10001',country='United States',formatted='123 Example Street, Sample City, NY 10001, United States')]}) if 'example' in query.lower() or '123' in query else []
        return dict(status='fixture',suggestions=rows,message='Synthetic address suggestions. No external provider contacted.')
    with _lock:
        if time.monotonic()-_last_call<0.4:return dict(status='limited',suggestions=[],message='Please pause briefly, then continue typing. Manual entry is always available.')
        _last_call=time.monotonic()
    if state['provider']=='Google Maps':
        from google_addresses import suggest
        try:return suggest(query.strip(),session)
        except Unavailable:return dict(status='unavailable',suggestions=[],message='Google address suggestions are unavailable. Check Places API activation and key restrictions, or enter manually.')
    try:return dict(status='ready',suggestions=normalize(fetch(query.strip(),os.environ['REGFIRE_GEOAPIFY_API_KEY'])),message='Suggestions by Geoapify. Check the address and add apartment or suite details manually.')
    except Unavailable:return dict(status='unavailable',suggestions=[],message='Address suggestions are temporarily unavailable. Continue with manual entry.')
