"""Resolve presentation from the owning event without rewriting flow drafts."""
import copy
import psycopg
FIELDS = ('intro_font', 'background_mode', 'background_color', 'background_asset_id', 'background_fade')

def apply(store, event, page):
    owner = event.get('parent_event_id') or event['id']
    with store.connect() as conn:
        row = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(psycopg.sql.Identifier(store.schema, 'welcome_pages')), (owner,)).fetchone()
    welcome = row[0] if row else {}
    result = copy.deepcopy(page)
    appearance = result.setdefault('appearance', {})
    appearance.update(intro_font=welcome.get('title_font', welcome.get('about_font','default')), background_mode=welcome.get('background_mode', 'image' if welcome.get('background_asset_id') else 'color'), background_color=welcome.get('background_color','#ffffff'), background_asset_id=welcome.get('background_asset_id'), background_fade=welcome.get('background_fade',80), background_owner_id=owner)
    appearance['event_logo_asset_id'] = welcome.get('logo_asset_id')
    appearance['event_logo_owner_id'] = owner
    if isinstance(appearance.get('footer'),dict):
        appearance['footer']['font'] = appearance['intro_font']
    result['theme_owner_id'] = owner
    return result
