"""Registration-page draft definitions; never attendee submissions."""
import re

CURRENCIES = {'USD': 2, 'EUR': 2, 'GBP': 2, 'CAD': 2, 'AUD': 2, 'JPY': 0}

FIELD_TYPES = {'text', 'email', 'tel', 'textarea', 'select', 'radio', 'checkbox', 'address'}
ADDRESS_PARTS = (
    ('line1', 'Address line 1'), ('line2', 'Address line 2'),
    ('city', 'City'), ('region', 'State / province / region'),
    ('postal', 'Postal code'), ('country', 'Country'),
)


def starter(event):
    return dict(event_id=event['id'], title=('Register for ' + event['name'])[:200], intro='',
                status='draft', updated=None, currency='USD',
                fields=[dict(id='first-name', label='First name', type='text', required=True, options=[], visible_to=None),
                        dict(id='last-name', label='Last name', type='text', required=True, options=[], visible_to=None),
                        dict(id='email', label='Email', type='email', required=True, options=[], visible_to=None),
                        dict(id='phone', label='Phone', type='tel', required=False, options=[], visible_to=None),
                        dict(id='cell-phone', label='Cell phone', type='tel', required=False, options=[], visible_to=None),
                        dict(id='address', label='Address', type='address', required=False, options=[], visible_to=None)],
                regtypes=[dict(id='attendee', name='Attendee', price_minor=0)])


def text(value, name, limit, required=False):
    if not isinstance(value, str): raise ValueError(f'{name} must be text.')
    value = value.strip()
    if required and not value: raise ValueError(f'{name} is required.')
    if len(value) > limit: raise ValueError(f'{name} must be {limit} characters or fewer.')
    return value


def identity(value, seen, kind):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError(f'Invalid {kind} ID.')
    if value in seen: raise ValueError(f'{kind} IDs must be unique.')
    seen.add(value)
    return value


def validate_page(data, zone_name='UTC'):
    if not isinstance(data, dict): raise ValueError('A registration page object is required.')
    result = dict(title=text(data.get('title'), 'Page title', 200, True),
                  intro=text(data.get('intro', ''), 'Introduction', 5000))
    currency = data.get('currency')
    if not isinstance(currency, str) or currency not in CURRENCIES: raise ValueError('Choose a supported currency.')
    result['currency'] = currency
    promos=data.get('promo_codes',[])
    if not isinstance(promos,list) or len(promos)>1000: raise ValueError('Use up to 1000 promo codes.')
    result['promo_codes']=[]; promo_seen=set()
    for promo in promos:
        if not isinstance(promo,dict): raise ValueError('Each promo code must be an object.')
        code=text(promo.get('code'),'Promo code',80,True).upper()
        if code in promo_seen: raise ValueError('Promo codes must be unique (case-insensitive).')
        promo_seen.add(code)
        kind=promo.get('type'); amount=promo.get('amount',0); enabled=promo.get('enabled',True)
        if kind not in ('free','percent','fixed'): raise ValueError('Choose free, percent, or fixed discount.')
        if type(enabled) is not bool: raise ValueError('Promo enabled must be true or false.')
        if type(amount) not in (int,float) or not 0<=amount<=999999: raise ValueError('Enter a valid promo amount.')
        if kind=='percent' and not 0<amount<=100: raise ValueError('Percentage discount must be greater than 0 and at most 100.')
        if kind=='fixed' and (amount<=0 or round(amount,2)!=amount): raise ValueError('Fixed discounts must be positive with at most two decimal places.')
        allotment=promo.get('allotment')
        if allotment is not None and (type(allotment) is not int or not 0<=allotment<=2147483647): raise ValueError('Promo allotment must be a whole number of 0 or more, or blank for unlimited.')
        result['promo_codes'].append(dict(code=code,type=kind,amount=0 if kind=='free' else amount,enabled=enabled,allotment=allotment))
    fields = data.get('fields')
    if not isinstance(fields, list) or not 1 <= len(fields) <= 50:
        raise ValueError('Include between 1 and 50 registration fields.')
    result['fields'] = []; seen = set()
    for index, field in enumerate(fields, 1):
        if not isinstance(field, dict): raise ValueError('Each field must be an object.')
        field_id = identity(field.get('id'), seen, 'Field')
        label = text(field.get('label'), f'Field {index} label', 120, True)
        kind = field.get('type')
        if not isinstance(kind, str) or kind not in FIELD_TYPES: raise ValueError(f'Choose a supported type for field {index}.')
        required = field.get('required')
        if type(required) is not bool: raise ValueError(f'Field {index} required setting must be true or false.')
        options = field.get('options', [])
        if not isinstance(options, list): raise ValueError(f'Field {index} choices must be a list.')
        if kind in ('select', 'radio'):
            if not 2 <= len(options) <= 30: raise ValueError(f'Field {index} needs 2–30 choices.')
            options = [text(option, f'Field {index} choice', 120, True) for option in options]
            if len({option.casefold() for option in options}) != len(options): raise ValueError(f'Field {index} choices must be unique.')
        else:
            options = []
        sms_consent=field.get('sms_consent', kind=='tel' and (field_id=='cell-phone' or bool(re.search(r'cell|mobile',label,re.I))))
        if type(sms_consent) is not bool: raise ValueError('Text-message consent setting must be true or false.')
        result['fields'].append(dict(id=field_id, label=label, type=kind, required=required, options=options, visible_to=field.get('visible_to'), sms_consent=sms_consent))
    regtypes = data.get('regtypes')
    if not isinstance(regtypes, list) or not 1 <= len(regtypes) <= 30:
        raise ValueError('Include between 1 and 30 RegTypes.')
    result['regtypes'] = []; seen = set(); names = set()
    for index, regtype in enumerate(regtypes, 1):
        if not isinstance(regtype, dict): raise ValueError('Each RegType must be an object.')
        type_id = identity(regtype.get('id'), seen, 'RegType')
        name = text(regtype.get('name'), f'RegType {index} name', 80, True)
        if name.casefold() in names: raise ValueError('RegType names must be unique.')
        price = regtype.get('price_minor')
        if type(price) is not int or not 0 <= price <= 99999999:
            raise ValueError(f'RegType {index} price must be an integer from 0 to 99999999 minor units.')
        show_on_welcome = regtype.get('show_on_welcome', True)
        if type(show_on_welcome) is not bool: raise ValueError('Show on welcome page must be true or false.')
        rates, use_default = validate_rates(regtype, zone_name)
        names.add(name.casefold()); result['regtypes'].append(dict(id=type_id, name=name, price_minor=price, rates=rates, use_default=use_default, show_on_welcome=show_on_welcome))
    for field in result['fields']:
        visible = field['visible_to']
        if visible is not None:
            if not isinstance(visible, list) or not visible or any(not isinstance(item, str) for item in visible):
                raise ValueError(f"Choose at least one RegType for {field['label']}, or show it to all types.")
            if len(set(visible)) != len(visible) or any(item not in seen for item in visible):
                raise ValueError(f"{field['label']} references a duplicate or removed RegType. Update its visibility.")
    appearance=data.get('appearance',{})
    if not isinstance(appearance,dict): raise ValueError('Appearance must be an object.')
    normalized={}
    import uuid
    for key in ('logo_asset_id','background_asset_id'):
        value=appearance.get(key)
        if value is not None:
            try:
                if not isinstance(value,str): raise ValueError()
                value=str(uuid.UUID(value))
            except ValueError: raise ValueError('Invalid page image reference.')
        normalized[key]=value
    fade=appearance.get('background_fade',80)
    if type(fade) is not int or not 0<=fade<=100: raise ValueError('Background fade must be an integer from 0 to 100.')
    normalized['background_fade']=fade
    for key,default in [('title_color','#24242a'),('intro_color','#555c68')]:
        value=appearance.get(key,default)
        if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value): raise ValueError('Choose a valid title or introduction color.')
        normalized[key]=value

    from welcome import FONT_IDS
    font=appearance.get('intro_font','default')
    if not isinstance(font,str) or font not in FONT_IDS: raise ValueError('Choose a supported introduction font.')
    normalized['intro_font']=font

    footer=appearance.get('footer',{})
    if not isinstance(footer,dict): raise ValueError('Footer must be an object.')
    enabled=footer.get('enabled',False)
    if type(enabled) is not bool: raise ValueError('Footer enabled must be true or false.')
    normalized['footer']={'enabled':enabled}
    footer_font=footer.get('font','default')
    if footer_font not in FONT_IDS:raise ValueError('Choose a supported footer font.')
    footer_color=footer.get('color','#f5f3f0')
    if not isinstance(footer_color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',footer_color):raise ValueError('Choose a valid footer font color.')
    logo=footer.get('logo_asset_id')
    if logo is not None and (not isinstance(logo,str) or not re.fullmatch(r'[a-f0-9-]{36}',logo)):raise ValueError('Choose a valid footer logo.')
    normalized['footer'].update(font=footer_font,color=footer_color,logo_asset_id=logo)
    normalized['footer']['heading']=text(footer.get('heading',''), 'Footer heading', 120)
    normalized['footer']['message']=text(footer.get('message',''), 'Footer message', 2000)
    normalized['footer']['hours']=text(footer.get('hours',''), 'Footer hours', 200)
    normalized['footer']['email']=text(footer.get('email',''), 'Footer email', 254)
    normalized['footer']['phone']=text(footer.get('phone',''), 'Footer phone', 80)
    normalized['footer']['links']=text(footer.get('links',''), 'Footer links', 4000)
    normalized['footer']['facebook']=text(footer.get('facebook',''), 'Footer facebook', 500)
    normalized['footer']['instagram']=text(footer.get('instagram',''), 'Footer instagram', 500)
    normalized['footer']['linkedin']=text(footer.get('linkedin',''), 'Footer linkedin', 500)
    normalized['footer']['youtube']=text(footer.get('youtube',''), 'Footer youtube', 500)
    normalized['footer']['x']=text(footer.get('x',''), 'Footer x', 500)

    from urllib.parse import urlsplit
    for key in ['facebook', 'instagram', 'linkedin', 'youtube', 'x']:
        value=normalized['footer'][key]
        if value and (urlsplit(value).scheme not in ('http','https') or not urlsplit(value).netloc): raise ValueError('Social links must use http or https addresses.')
    for line in normalized['footer']['links'].splitlines():
        if not line.strip(): continue
        label,sep,url=line.partition('|')
        if not sep or not label.strip(): raise ValueError('Footer links need Label | https://address on each line.')
        parsed=urlsplit(url.strip())
        if parsed.scheme not in ('http','https') or not parsed.netloc: raise ValueError('Footer links must use http or https addresses.')
    result['appearance']=normalized
    return result


def local_instant(value, zone_name, label):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
        raise ValueError(f'{label} must use YYYY-MM-DDTHH:MM.')
    try:
        naive = datetime.fromisoformat(value)
        zone = ZoneInfo(zone_name)
        aware = naive.replace(tzinfo=zone, fold=0)
        instant = aware.astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None) != naive: raise ValueError()
        return instant
    except (ValueError, OverflowError):
        raise ValueError(f'{label} is not a valid local time in {zone_name}.')


def validate_rates(regtype, zone_name):
    from datetime import datetime, timezone
    rates = regtype.get('rates', [])
    fallback = regtype.get('use_default', True)
    if type(fallback) is not bool: raise ValueError('Default rate setting must be true or false.')
    if not isinstance(rates, list) or len(rates) > 20: raise ValueError('Use at most 20 rate periods per RegType.')
    seen=set(); names=set(); normalized=[]; windows=[]
    for rate in rates:
        if not isinstance(rate, dict): raise ValueError('Each rate period must be an object.')
        rate_id=identity(rate.get('id'),seen,'Rate')
        name=text(rate.get('name'),'Rate name',80,True)
        if name.casefold() in names: raise ValueError('Rate names must be unique within a RegType.')
        names.add(name.casefold())
        price=rate.get('price_minor')
        if type(price) is not int or not 0 <= price <= 99999999: raise ValueError('Rate prices must be integers from 0 to 99999999 minor units.')
        start=text(rate.get('start',''),'Rate start',16)
        end=text(rate.get('end',''),'Rate end',16)
        if not start and not end: raise ValueError('A dated rate needs a start or end. Use the default rate for an undated price.')
        lower=local_instant(start,zone_name,'Rate start') if start else datetime.min.replace(tzinfo=timezone.utc)
        upper=local_instant(end,zone_name,'Rate end') if end else datetime.max.replace(tzinfo=timezone.utc)
        if upper<=lower: raise ValueError('A rate must end after it starts.')
        windows.append((lower,upper,name))
        normalized.append(dict(id=rate_id,name=name,price_minor=price,start=start,end=end))
    windows.sort(key=lambda item:item[0])
    for previous,current in zip(windows,windows[1:]):
        if current[0]<previous[1]: raise ValueError(f'Rate periods overlap: {previous[2]} and {current[2]}. End times are exclusive.')
    return normalized,fallback


def applicable_rate(regtype, instant, zone_name):
    for rate in regtype.get('rates',[]):
        start=local_instant(rate['start'],zone_name,'Rate start') if rate['start'] else None
        end=local_instant(rate['end'],zone_name,'Rate end') if rate['end'] else None
        if (start is None or instant>=start) and (end is None or instant<end):
            return dict(status='scheduled',rate_id=rate['id'],name=rate['name'],price_minor=rate['price_minor'],start=rate['start'],end=rate['end'])
    if regtype.get('use_default',True):
        return dict(status='default',rate_id=None,name='Default rate',price_minor=regtype['price_minor'],start='',end='',message='No dated period applies. The enabled default rate is used.')
    return dict(status='unavailable',rate_id=None,name='No active rate',price_minor=None,start='',end='',message='No dated period applies and the default rate is disabled. No price is offered at this time.')


def pricing_preview(data, zone_name, at=''):
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    page=validate_page(data,zone_name)
    instant=local_instant(at,zone_name,'Preview time') if at else datetime.now(timezone.utc)
    return dict(timezone=zone_name,at=instant.astimezone(ZoneInfo(zone_name)).isoformat(),currency=page['currency'],
                regtypes={r['id']:applicable_rate(r,instant,zone_name) for r in page['regtypes']})
