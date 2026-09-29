#!/usr/bin/env python3
"""Build the 25-second Swarm Pepe film from verified on-chain SVG bytes."""

import json
import math
from pathlib import Path
import struct
import subprocess
import wave


ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT, FPS, SECONDS = 960, 540, 30, 25
BG = (10, 19, 24)
PANEL = (22, 34, 39)
LINE = (48, 72, 70)
LIME = (202, 244, 101)
CREAM = (237, 232, 204)
MUTED = (117, 145, 139)
ORANGE = (252, 137, 79)

# Original seven-row bitmap alphabet used for cards and titles. Pixel portraits
# themselves come exclusively from the SVGs returned by the Ethereum renderer.
FONT = {
    'A': ('01110','10001','10001','11111','10001','10001','10001'),
    'B': ('11110','10001','10001','11110','10001','10001','11110'),
    'C': ('01111','10000','10000','10000','10000','10000','01111'),
    'D': ('11110','10001','10001','10001','10001','10001','11110'),
    'E': ('11111','10000','10000','11110','10000','10000','11111'),
    'F': ('11111','10000','10000','11110','10000','10000','10000'),
    'G': ('01111','10000','10000','10111','10001','10001','01111'),
    'H': ('10001','10001','10001','11111','10001','10001','10001'),
    'I': ('11111','00100','00100','00100','00100','00100','11111'),
    'J': ('00111','00010','00010','00010','10010','10010','01100'),
    'K': ('10001','10010','10100','11000','10100','10010','10001'),
    'L': ('10000','10000','10000','10000','10000','10000','11111'),
    'M': ('10001','11011','10101','10101','10001','10001','10001'),
    'N': ('10001','11001','10101','10011','10001','10001','10001'),
    'O': ('01110','10001','10001','10001','10001','10001','01110'),
    'P': ('11110','10001','10001','11110','10000','10000','10000'),
    'Q': ('01110','10001','10001','10001','10101','10010','01101'),
    'R': ('11110','10001','10001','11110','10100','10010','10001'),
    'S': ('01111','10000','10000','01110','00001','00001','11110'),
    'T': ('11111','00100','00100','00100','00100','00100','00100'),
    'U': ('10001','10001','10001','10001','10001','10001','01110'),
    'V': ('10001','10001','10001','10001','10001','01010','00100'),
    'W': ('10001','10001','10001','10101','10101','10101','01010'),
    'X': ('10001','10001','01010','00100','01010','10001','10001'),
    'Y': ('10001','10001','01010','00100','00100','00100','00100'),
    'Z': ('11111','00001','00010','00100','01000','10000','11111'),
    '0': ('01110','10001','10011','10101','11001','10001','01110'),
    '1': ('00100','01100','00100','00100','00100','00100','01110'),
    '2': ('01110','10001','00001','00010','00100','01000','11111'),
    '3': ('11110','00001','00001','01110','00001','00001','11110'),
    '4': ('00010','00110','01010','10010','11111','00010','00010'),
    '5': ('11111','10000','10000','11110','00001','00001','11110'),
    '6': ('01111','10000','10000','11110','10001','10001','01110'),
    '7': ('11111','00001','00010','00100','01000','01000','01000'),
    '8': ('01110','10001','10001','01110','10001','10001','01110'),
    '9': ('01110','10001','10001','01111','00001','00001','11110'),
    '#': ('01010','11111','01010','01010','11111','01010','00000'),
    '/': ('00001','00001','00010','00100','01000','10000','10000'),
    ':': ('00000','00100','00100','00000','00100','00100','00000'),
    '.': ('00000','00000','00000','00000','00000','00110','00110'),
    '$': ('00100','01111','10100','01110','00101','11110','00100'),
    '-': ('00000','00000','00000','11111','00000','00000','00000'),
    'a': ('00000','01110','00001','01111','10001','10001','01111'),
    'b': ('10000','10000','11110','10001','10001','10001','11110'),
    'd': ('00001','00001','01111','10001','10001','10001','01111'),
    'e': ('00000','01110','10001','11111','10000','10001','01110'),
    'g': ('00000','01111','10001','10001','01111','00001','01110'),
    'm': ('00000','11010','10101','10101','10101','10101','10101'),
    'n': ('00000','11110','10001','10001','10001','10001','10001'),
    'r': ('00000','10110','11001','10000','10000','10000','10000'),
    's': ('00000','01111','10000','01110','00001','00001','11110'),
    't': ('00100','00100','11111','00100','00100','00101','00010'),
    'w': ('00000','10001','10001','10101','10101','10101','01010'),
    'y': ('00000','10001','10001','10001','01111','00001','01110'),
    ' ': ('00000',)*7,
}


class Canvas:
    def __init__(self, background):
        self.pixels = bytearray(background)

    def rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(WIDTH, x+w), min(HEIGHT, y+h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1-x0)
        for yy in range(y0, y1):
            start = (yy*WIDTH+x0)*3
            self.pixels[start:start+len(row)] = row

    def border(self, x, y, w, h, color, thickness=2):
        self.rect(x, y, w, thickness, color)
        self.rect(x, y+h-thickness, w, thickness, color)
        self.rect(x, y, thickness, h, color)
        self.rect(x+w-thickness, y, thickness, h, color)

    def text(self, s, x, y, scale, color):
        for ch in s:
            glyph = FONT.get(ch, FONT[' '])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == '1':
                        self.rect(x+gx*scale, y+gy*scale, scale, scale, color)
            x += 6*scale

    def sprite(self, sprite, x, y, size):
        data = sprite[size]
        for yy in range(size):
            if y+yy < 0 or y+yy >= HEIGHT:
                continue
            x0, x1 = max(0, x), min(WIDTH, x+size)
            if x1 <= x0:
                continue
            src_start = (yy*size+x0-x)*3
            dst_start = ((y+yy)*WIDTH+x0)*3
            self.pixels[dst_start:dst_start+(x1-x0)*3] = data[src_start:src_start+(x1-x0)*3]


def width_of(text, scale):
    return len(text)*6*scale


def background():
    c = Canvas(bytes(BG) * (WIDTH*HEIGHT))
    for x in range(0, WIDTH, 24):
        c.rect(x, 0, 1, HEIGHT, (17, 29, 32))
    for y in range(0, HEIGHT, 24):
        c.rect(0, y, WIDTH, 1, (17, 29, 32))
    c.border(21, 20, 918, 500, LINE, 2)
    c.rect(30, 44, 900, 2, LINE)
    c.rect(30, 494, 900, 2, LINE)
    c.text('SWARM / PEPE', 42, 28, 2, LIME)
    c.text('ETHEREUM MAINNET', 726, 28, 2, MUTED)
    c.text('ON CHAIN / 24 X 24', 42, 505, 2, MUTED)
    return bytes(c.pixels)


def load_sprites():
    provenance = json.loads((ROOT/'assets/provenance.json').read_text())
    records = {r['token_id']: r for r in provenance['tokens']}
    if any(i not in records for i in range(1, 13)):
        raise RuntimeError('Missing required on-chain token SVG')
    sprites = {}
    for token_id in range(1, 13):
        svg = ROOT/'assets'/records[token_id]['svg']
        raw = subprocess.check_output([
            'ffmpeg', '-v', 'error', '-i', str(svg), '-frames:v', '1',
            '-vf', 'scale=24:24:flags=neighbor', '-f', 'rawvideo',
            '-pix_fmt', 'rgb24', '-'])
        if len(raw) != 24*24*3:
            raise RuntimeError(f'Bad raster size for #{token_id}')
        sprites[token_id] = {}
        for size in (96, 168, 288, 336):
            scale = size//24
            rows = []
            for y in range(24):
                row = b''.join(raw[(y*24+x)*3:(y*24+x+1)*3]*scale for x in range(24))
                rows.extend([row]*scale)
            sprites[token_id][size] = b''.join(rows)
    return sprites


def common(c, frame):
    # The lower border is a 25-second playback ruler.
    c.rect(30, 493, round(900*frame/(FPS*SECONDS-1)), 3, LIME)
    c.text(f'{frame//FPS:02d} / 25 SEC', 770, 505, 2, CREAM)
    blink = (frame//12) % 2 == 0
    c.rect(914, 32, 8, 8, ORANGE if blink else LINE)


def intro(c, frame, sprites):
    c.text('SWARM', 62, 138, 8, CREAM)
    c.text('PEPE', 62, 218, 8, LIME)
    c.rect(63, 301, 324, 3, ORANGE)
    c.text('MINTED SIGNALS', 63, 331, 3, CREAM)
    c.text('12 ORIGINAL ON-CHAIN PORTRAITS', 63, 381, 2, MUTED)
    c.text('RENDERED FROM THEIR REVEALED SEEDS', 63, 408, 2, MUTED)
    if frame >= 10:
        bob = 0 if (frame//18)%2 == 0 else -4
        c.rect(551, 91+bob, 316, 340, PANEL)
        c.border(551, 91+bob, 316, 340, LIME, 2)
        c.sprite(sprites[1], 565, 105+bob, 288)
        c.text('#0001', 576, 402+bob, 3, LIME)
        c.text('01 / 12', 763, 407+bob, 2, MUTED)
    for i in range(13):
        h = 9+((i*17+frame//3)%5)*7
        c.rect(67+i*17, 452-h, 9, h, LIME if i <= frame//7 else LINE)


def gallery(c, frame, sprites):
    c.text('THE FIRST SIGNALS', 60, 81, 4, CREAM)
    c.text('MINTED / REVEALED / RENDERED', 61, 126, 2, MUTED)
    local = frame - 3*FPS
    for idx, token_id in enumerate(range(2, 6)):
        if local < idx*19:
            continue
        x = 47 + idx*224
        y = 173
        c.rect(x, y, 200, 261, PANEL)
        c.border(x, y, 200, 261, LIME if (local//15)%4 == idx else LINE, 2)
        c.sprite(sprites[token_id], x+16, y+16, 168)
        c.text(f'#{token_id:04d}', x+17, y+204, 3, CREAM)
        c.rect(x+16, y+244, 168, 3, ORANGE if idx%2 else LIME)
    c.text('ONE SEED. ONE DISTINCT PEPE.', 61, 459, 2, LIME)


def hero(c, frame, sprites):
    slot = min(3, (frame-9*FPS)//(2*FPS))
    token_id = 6+slot
    local = (frame-9*FPS)%(2*FPS)
    c.text('ONE SEED', 62, 118, 5, CREAM)
    c.text('ONE PEPE', 62, 173, 5, LIME)
    c.rect(63, 244, 337, 3, ORANGE)
    c.text(f'#{token_id:04d}', 62, 272, 6, CREAM)
    c.text('MINTED ON ETHEREUM', 64, 351, 2, MUTED)
    c.text('DRAWN BY PIXELART', 64, 377, 2, MUTED)
    c.text(f'PORTRAIT {slot+1:02d} / 04', 64, 420, 2, LIME)
    c.rect(501, 70, 386, 403, PANEL)
    c.border(501, 70, 386, 403, LIME, 2)
    c.sprite(sprites[token_id], 526, 93, 336)
    c.text(f'SEED {slot+1:02d} / SIGNAL ACTIVE', 532, 440, 2, CREAM)
    for i in range(16):
        h = 6+((i*7+local//4)%6)*5
        c.rect(64+i*20, 478-h, 10, h, LIME if i <= local//4 else LINE)


def mosaic(c, frame, sprites):
    local = frame-17*FPS
    title = 'THE SWARM IS MANY'
    c.text(title, (WIDTH-width_of(title, 4))//2, 68, 4, CREAM)
    for idx, token_id in enumerate(range(1, 13)):
        if local < idx*10:
            continue
        x = 162+(idx%4)*162
        y = 113+(idx//4)*123
        c.rect(x, y, 150, 117, PANEL)
        active = local >= 6*FPS and idx == (local//12)%12
        c.border(x, y, 150, 117, ORANGE if active else LINE, 2)
        c.sprite(sprites[token_id], x+27, y+4, 96)
        c.text(f'#{token_id:04d}', x+45, y+102, 2, CREAM)
    if local >= 6*FPS:
        c.rect(295, 496, 370, 28, BG)
        c.text('generated by $IMD swarm', 336, 505, 2, LIME)


def write_audio(path):
    rate = 22050
    count = SECONDS*rate
    notes = [220, 261.63, 329.63, 392, 329.63, 261.63, 246.94, 329.63]
    bass = [110, 110, 130.81, 98, 110, 110, 146.83, 98]
    pcm = bytearray()
    for i in range(count):
        t = i/rate
        beat = t*2  # 120 bpm, 50 beats total
        step = int(beat*2)
        frac = beat*2-step
        note = notes[(step//2)%len(notes)]
        low = bass[(int(beat)//2)%len(bass)]
        # Soft square arpeggio plus a round bass and a sparse beat.
        phase = (t*note)%1
        lead = (0.7 if phase<0.5 else -0.7) * math.exp(-frac*2.5)
        lead += 0.18*math.sin(2*math.pi*note*t)
        bass_env = math.exp(-(beat%1)*3.2)
        low_voice = 0.55*math.sin(2*math.pi*low*t)*bass_env
        kick_age = (beat%1)/2
        kick = 0.45*math.sin(2*math.pi*(60+85*math.exp(-kick_age*25))*kick_age)*math.exp(-kick_age*21)
        hat_age = (beat*2)%1/4
        noise = math.sin(i*12.9898)*math.sin(i*78.233)
        hat = 0.13*noise*math.exp(-hat_age*75)
        pad = 0.12*math.sin(2*math.pi*55*t)
        fade = min(1, t/0.3, (SECONDS-t)/0.55)
        sample = max(-1, min(1, (lead*0.24+low_voice*0.27+kick*0.36+hat+pad)*fade))
        pcm.extend(struct.pack('<h', int(sample*30000)))
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)


def main():
    (ROOT/'artifacts').mkdir(exist_ok=True)
    (ROOT/'test/scratch').mkdir(parents=True, exist_ok=True)
    sound = ROOT/'test/scratch'/'original_score.wav'
    write_audio(sound)
    sprites = load_sprites()
    base = background()
    out = ROOT/'artifacts'/'video.mp4'
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}',
           '-r', str(FPS), '-i', '-', '-i', str(sound),
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '15',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
           '-movflags', '+faststart', '-t', str(SECONDS), str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for frame in range(FPS*SECONDS):
            c = Canvas(base)
            if frame < 3*FPS:
                intro(c, frame, sprites)
            elif frame < 9*FPS:
                gallery(c, frame, sprites)
            elif frame < 17*FPS:
                hero(c, frame, sprites)
            else:
                mosaic(c, frame, sprites)
            common(c, frame)
            proc.stdin.write(c.pixels)
            if frame%150 == 0:
                print(f'frame {frame}/{FPS*SECONDS}', flush=True)
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError('ffmpeg encoding failed')
    print(out)


if __name__ == '__main__':
    main()
