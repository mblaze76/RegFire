"""Additive background choices shared by welcome, registration and footer."""
import re,uuid

def validate(data, color='#ffffff', fade=80):
    mode=data.get('background_mode','image' if data.get('background_asset_id') else 'color')
    if mode not in ('image','color'):raise ValueError('Choose image or color for the background.')
    color=data.get('background_color',color)
    if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Choose a valid background color.')
    fade=data.get('background_fade',fade)
    if type(fade) is not int or not 0<=fade<=100:raise ValueError('Background transparency must be 0 to 100.')
    image=data.get('background_asset_id')
    if image is not None:
        try:image=str(uuid.UUID(image))
        except (ValueError,TypeError,AttributeError):raise ValueError('Choose a valid background image.')
    return dict(background_mode=mode,background_color=color.lower(),background_fade=fade,background_asset_id=image)
