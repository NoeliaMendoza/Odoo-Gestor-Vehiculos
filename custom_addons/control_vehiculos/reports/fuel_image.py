"""Dibuja un medidor de combustible que se puede insertar en HTML y Word."""
from functools import lru_cache
from io import BytesIO
from math import cos, sin, pi

from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=102)
def fuel_image(level):
    """Devuelve PNG; un nivel pendiente nunca se representa como tanque vacío."""
    scale = 2
    image = Image.new('RGB', (640 * scale, 330 * scale), 'white')
    draw = ImageDraw.Draw(image)
    def font(size):
        for filename in ('arial.ttf', 'DejaVuSans.ttf'):
            try:
                return ImageFont.truetype(filename, size * scale)
            except OSError:
                continue
        return ImageFont.load_default()
    def text(x, y, value, size=18, fill='#42566c'):
        draw.text((x * scale, y * scale), value, font=font(size), fill=fill, anchor='mm')
    def line(points, fill, width=3):
        draw.line([(int(x * scale), int(y * scale)) for x, y in points], fill=fill, width=width * scale)
    cx, cy, radius = 320, 252, 163
    box = tuple(int(v * scale) for v in (cx-radius,cy-radius,cx+radius,cy+radius))
    draw.arc(box, 180, 270, fill='#fde3e5', width=16*scale)
    draw.arc(box, 270, 360, fill='#d9f8e6', width=16*scale)
    for percent in (0, 25, 50, 75, 100):
        angle = pi * (1-percent/100)
        line([(cx+(radius-15)*cos(angle),cy-(radius-15)*sin(angle)),
              (cx+(radius+3)*cos(angle),cy-(radius+3)*sin(angle))], '#8495a7')
    text(320, 40, 'Sin registrar' if level is None else f'{level} %', 30)
    text(144, 283, '0 %', 17)
    text(320, 74, '50 %', 17)
    text(501, 283, '100 %', 17)
    # Símbolo de surtidor, trazado propio para no depender de fuentes de iconos.
    line([(299,210),(299,163),(327,163),(327,210),(295,210),(331,210)], '#42566c', 3)
    line([(304,178),(321,178),(321,169),(304,169),(304,178)], '#42566c', 2)
    line([(327,185),(336,185),(336,208),(345,208),(345,177),(335,165)], '#42566c', 3)
    if level is not None:
        angle = pi * (1-max(0,min(100,level))/100)
        tip = (cx+138*cos(angle),cy-138*sin(angle))
        points = [(cx-8*sin(angle),cy-8*cos(angle)),tip,(cx+8*sin(angle),cy+8*cos(angle))]
        draw.polygon([(int(x*scale),int(y*scale)) for x,y in points], fill='#334155')
        draw.ellipse(((cx-9)*scale,(cy-9)*scale,(cx+9)*scale,(cy+9)*scale), fill='#334155')
    text(320, 315, 'Mínimo requerido: medio tanque (50 %)', 16)
    stream = BytesIO()
    image.resize((640,330), Image.Resampling.LANCZOS).save(stream, format='PNG')
    return stream.getvalue()
