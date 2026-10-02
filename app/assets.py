"""Validate and normalize user-supplied page images; filenames never come from users."""
import io, warnings
from PIL import Image, ImageOps, UnidentifiedImageError
MAX_UPLOAD = 8 * 1024 * 1024


def normalize_image(content):
    if not content or len(content)>MAX_UPLOAD: raise ValueError('Choose an image no larger than 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in ('PNG','JPEG','WEBP'): raise ValueError('Use a PNG, JPEG or WebP image. SVG and animated formats are not accepted.')
                if getattr(source,'n_frames',1)!=1: raise ValueError('Animated images are not supported.')
                w,h=source.size
                if max(w,h)>6000 or w*h>16000000: raise ValueError('Images must be at most 6000 pixels per side and 16 megapixels.')
                source.verify()
            with Image.open(io.BytesIO(content)) as source:
                source=ImageOps.exif_transpose(source)
                source=source.convert('RGBA' if 'A' in source.getbands() or 'transparency' in source.info else 'RGB')
                source.thumbnail((2560,2560),Image.Resampling.LANCZOS)
                clean=Image.new(source.mode,source.size);clean.paste(source)
                buffer=io.BytesIO();clean.save(buffer,format='PNG',compress_level=6)
                output=buffer.getvalue()
                if len(output)>16*1024*1024: raise ValueError('Normalized image is too large. Choose a smaller image.')
                return output
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('This file is not a supported, valid image.')
