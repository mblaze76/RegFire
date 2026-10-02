"""Server-side Google Places address suggestions; never expose API credentials."""
import json, re, time, http.client
from pathlib import Path
from urllib.parse import urlencode
from membership import public_addresses, PinnedHTTPS, Unavailable

KEY_FILE=Path(__file__).resolve().parent/'.local/google-maps-key'
def key():
    import os
    value=os.environ.get('REGFIRE_GOOGLE_MAPS_API_KEY','')
    if not value and KEY_FILE.is_file():
        if KEY_FILE.stat().st_mode & 0o077: return ''
        value=KEY_FILE.read_text().strip()
    return value

def request(path,body=None,mask=''):
    credential=key()
    if not credential:raise Unavailable('Google Places is not configured.')
    host='places.googleapis.com';conn=PinnedHTTPS(host,public_addresses(host)[0])
    headers={'X-Goog-Api-Key':credential,'Accept':'application/json','Content-Type':'application/json'}
    if mask:headers['X-Goog-FieldMask']=mask
    try:
        conn.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=conn.getresponse();data=b'';deadline=time.monotonic()+10
        while len(data)<=131072:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise Unavailable('Address lookup timed out.')
            if conn.sock:conn.sock.settimeout(min(5,remaining))
            chunk=response.read1(min(8192,131073-len(data)))
            if not chunk:break
            data+=chunk
        if response.status!=200 or len(data)>131072:raise Unavailable('Google Places is unavailable. Check API activation and key restrictions.')
        return json.loads(data)
    except (OSError,ValueError,http.client.HTTPException):raise Unavailable('Google Places is unavailable.')
    finally:conn.close()

def token(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,36}',value):raise ValueError('Invalid address session.')
    return value

def suggest(query,session):
    result=request('/v1/places:autocomplete',{'input':query,'sessionToken':token(session)},'suggestions.placePrediction.placeId,suggestions.placePrediction.text.text')
    rows=[]
    for item in result.get('suggestions',[])[:5]:
        p=item.get('placePrediction',{});pid=p.get('placeId','');label=p.get('text',{}).get('text','')
        if isinstance(pid,str) and re.fullmatch(r'[\w-]{1,256}',pid) and isinstance(label,str):rows.append({'place_id':pid,'formatted':label[:500]})
    return {'status':'ready','provider':'google','suggestions':rows,'message':'Choose an address from Google Maps. This is not postal deliverability validation.'}

def normalize(data):
    components={}
    for c in data.get('addressComponents',[]):
        for t in c.get('types',[]):components[t]=c.get('longText','')[:500]
    return {'line1':' '.join(filter(None,[components.get('street_number'),components.get('route')])) or components.get('premise',''),
        'city':components.get('locality') or components.get('postal_town') or components.get('sublocality_level_1',''),
        'region':components.get('administrative_area_level_1',''),'postal':components.get('postal_code',''),
        'country':components.get('country',''),'formatted':data.get('formattedAddress','')[:500]}

def details(pid,session):
    if not isinstance(pid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,256}',pid):raise ValueError('Invalid place.')
    return normalize(request('/v1/places/'+pid+'?'+urlencode({'sessionToken':token(session)}),mask='addressComponents,formattedAddress'))
