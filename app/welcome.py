"""Welcome-page draft content validation."""
import uuid, re, json
from pathlib import Path
FONT_IDS = frozenset(("default","arial","georgia","trebuchet","verdana")) | frozenset(json.loads((Path(__file__).parent / "static/welcome-fonts.json").read_text()))
from urllib.parse import urlsplit

def validate(data):
    if not isinstance(data, dict): raise ValueError('A welcome page object is required.')
    color=data.get('about_color','#24242a')
    if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Choose a valid event details text color.')
    font=data.get('about_font','default')
    if not isinstance(font,str) or font not in FONT_IDS: raise ValueError('Choose a supported event details font.')
    title=data.get('title','Welcome to online registration')
    if not isinstance(title,str) or not title.strip() or len(title)>200:raise ValueError('Page title must contain 1 to 200 characters.')
    title_font=data.get('title_font','default')
    if not isinstance(title_font,str) or title_font not in FONT_IDS:raise ValueError('Choose a supported page title font.')
    title_color=data.get('title_color')
    if title_color is not None and (not isinstance(title_color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',title_color)):raise ValueError('Choose a valid page title color.')
    about = data.get('about', '')
    if not isinstance(about, str) or len(about) > 10000: raise ValueError('Event details must be text of at most 10,000 characters.')
    sponsors = data.get('sponsor_asset_ids', [])
    if not isinstance(sponsors, list) or len(sponsors) > 4: raise ValueError('Use up to four sponsor logos.')
    def asset(value):
        if not isinstance(value, str): raise ValueError('Invalid logo ID.')
        try: return str(uuid.UUID(value))
        except (ValueError, AttributeError): raise ValueError('Invalid logo ID.')
    def url(value):
        if not isinstance(value,str) or len(value)>2000: raise ValueError('Logo links must be URLs of at most 2,000 characters.')
        value=value.strip()
        if value:
            parsed=urlsplit(value)
            if parsed.scheme not in ('http','https') or not parsed.hostname or any(c.isspace() for c in value) or parsed.username is not None or parsed.password is not None:
                raise ValueError('Use a complete http or https website URL without spaces or embedded credentials.')
            try: parsed.port
            except ValueError: raise ValueError('Use a valid website URL port.')
        return value
    links=data.get('sponsor_urls', ['']*len(sponsors))
    if not isinstance(links,list) or len(links)!=len(sponsors): raise ValueError('Each sponsor must have one optional link.')
    buttons=data.get('buttons')
    if buttons is not None:
        if not isinstance(buttons,list) or len(buttons)>100: raise ValueError('Use at most 100 welcome buttons.')
        clean=[]; seen=set()
        for button in buttons:
            if not isinstance(button,dict):raise ValueError('Invalid welcome button.')
            identity=asset(button.get('id')); label=button.get('label','')
            if identity in seen:raise ValueError('Each welcome button needs a unique ID.')
            seen.add(identity)
            if not isinstance(label,str) or not label.strip() or len(label)>100:raise ValueError('Enter a button label of 1 to 100 characters.')
            destination=button.get('flow_id')
            clean.append(dict(id=identity,label=label.strip(),flow_id=asset(destination) if destination else None))
        buttons=clean
    background=data.get('background_asset_id')
    fade=data.get('background_fade',80)
    if type(fade) is not int or not 0<=fade<=100:raise ValueError('Background fade must be a whole number from 0 to 100.')
    logo = data.get('logo_asset_id')
    from background import validate as background_settings
    result = dict(title=title.strip(),title_font=title_font,title_color=title_color.lower() if title_color else None,background_asset_id=asset(background) if background else None, background_fade=fade, buttons=buttons, about_font=font, about_color=color.lower(), login_url=url(data.get('login_url','')), logo_url=url(data.get('logo_url','')), sponsor_urls=[url(value) for value in links], about=about, logo_asset_id=asset(logo) if logo is not None else None, sponsor_asset_ids=[asset(value) for value in sponsors])

    result.update(background_settings(data))
    return result
