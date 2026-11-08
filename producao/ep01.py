#!/usr/bin/env python3
"""Lucas - Episodio 1: renderiza o video (720x1280, 24 fps, ~58 s) com PIL + ffmpeg.

Uso:
    python3 producao/ep01.py preview  caminho/folha.png   # folha de contato
    python3 producao/ep01.py render   caminho/saida.mp4   # video final
"""
import glob, math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS, DUR = 720, 1280, 2, 24, 58.0
SKIN, HAIR, HAIR_D, BLUE = '#ffd6bd', '#f7d44a', '#d9a920', '#2f86e8'

FONT_PATH = (glob.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True) or [None])[0]


@lru_cache(None)
def font(size):
    return ImageFont.truetype(FONT_PATH, int(size)) if FONT_PATH else ImageFont.load_default()


def lerp_col(c0, c1, t):
    a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class G:
    """Canvas em coordenadas logicas 720x1280, desenhado com supersampling."""

    def __init__(s):
        s.im = Image.new('RGB', (W * S, H * S), 'white')
        s.d = ImageDraw.Draw(s.im)

    def ell(s, cx, cy, rx, ry, fill=None, ol=None, w=0):
        s.d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S],
                    fill=fill, outline=ol, width=int(w * S))

    def rect(s, x0, y0, x1, y1, fill=None, r=0, ol=None, w=0):
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        s.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=max(0, r) * S,
                              fill=fill, outline=ol, width=int(w * S))

    def poly(s, pts, fill):
        s.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(s, pts, fill, w):
        s.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=max(1, int(w * S)), joint='curve')

    def arc(s, cx, cy, rx, ry, a0, a1, fill, w):
        s.d.arc([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], a0, a1,
                fill=fill, width=max(1, int(w * S)))

    def text(s, x, y, t, size, fill, anchor='mm', stroke=0, sfill=None):
        s.d.text((x * S, y * S), t, font=font(size * S), fill=fill, anchor=anchor,
                 stroke_width=int(stroke * S), stroke_fill=sfill)

    def tw(s, t, size):
        return s.d.textlength(t, font=font(size * S)) / S

    def gradient(s, y0, y1, c0, c1):
        for y in range(int(y0), int(y1), 4):
            s.rect(0, y, W, y + 5, lerp_col(c0, c1, (y - y0) / max(1, y1 - y0)))

    def out(s):
        return s.im.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- personagens
def resolve(mouth, t):
    if mouth == 'talk':
        return 'open' if int(t * 9) % 2 == 0 else 'small'
    return mouth


def mouth_draw(g, hx, my, k, mouth):
    if mouth == 'smile':
        g.arc(hx, my - 10 * k, 26 * k, 22 * k, 20, 160, '#8a2d2d', 6 * k)
    elif mouth == 'open':
        g.ell(hx, my + 4 * k, 20 * k, 17 * k, '#7a1f2b'); g.ell(hx, my + 13 * k, 12 * k, 7 * k, '#ff7a8a')
    elif mouth == 'small':
        g.ell(hx, my + 2 * k, 13 * k, 9 * k, '#7a1f2b')
    elif mouth == 'o':
        g.ell(hx, my + 6 * k, 13 * k, 17 * k, '#7a1f2b')
    elif mouth == 'big':
        g.ell(hx, my + 4 * k, 28 * k, 24 * k, '#7a1f2b'); g.ell(hx, my + 16 * k, 17 * k, 9 * k, '#ff7a8a')


def arms(g, X, Y, k, sh_x, sh_y, L, armL, armR, sleeve, thick, hand_r=17):
    hands = {}
    for side, ang in ((-1, armL), (1, armR)):
        a = math.radians(ang)
        sx, sy = X(side * sh_x), Y(sh_y)
        dx, dy = side * math.sin(a), math.cos(a)
        ex, ey = sx + dx * L * k, sy + dy * L * k
        mx, my = sx + dx * L * k * .5, sy + dy * L * k * .5
        g.line([(sx, sy), (mx, my)], sleeve, thick * 1.25 * k)
        g.line([(mx, my), (ex, ey)], SKIN, thick * k)
        g.ell(ex, ey, hand_r * k, hand_r * k, SKIN)
        hands[side] = (ex, ey)
    return hands


def lucas(g, fx, fy, sc=1.0, mouth='smile', eyes='auto', armL=15, armR=15, fingers=0,
          shirt='#ff5c5c', pants='#3b5bdb', back=False, pack=None, brow=0, t=0.0):
    k = sc
    X = lambda v: fx + v * k
    Y = lambda v: fy + v * k
    mouth = resolve(mouth, t)
    if eyes == 'auto':
        eyes = 'blink' if (t % 3.3) < 0.13 else 'open'
    if pack and not back:
        g.rect(X(-80), Y(-255), X(80), Y(-55), pack, r=34 * k)
    for sx in (-1, 1):
        g.rect(X(sx * 30 - 19), Y(-85), X(sx * 30 + 19), Y(-15), pants, r=9 * k)
        g.ell(X(sx * 34), Y(-12), 27 * k, 15 * k, '#e63946')
    g.rect(X(-20), Y(-240), X(20), Y(-200), SKIN)
    g.rect(X(-58), Y(-215), X(58), Y(-70), shirt, r=32 * k)
    if pack and back:
        g.rect(X(-80), Y(-255), X(80), Y(-55), pack, r=34 * k)
        g.rect(X(-30), Y(-170), X(30), Y(-110), lerp_col(pack, '#000000', .2), r=12 * k)
    def do_arms():
        hands = arms(g, X, Y, k, 56, -195, 100, armL, armR, shirt, 28)
        if fingers and 1 in hands:
            ex, ey = hands[1]
            for i in range(fingers):
                ox = (i - (fingers - 1) / 2) * 11 * k
                g.rect(ex + ox - 5 * k, ey - 44 * k, ex + ox + 5 * k, ey - 8 * k, SKIN, r=5 * k)
    hx, hy = X(0), Y(-318)
    for sx in (-1, 1):
        g.ell(hx + sx * 100 * k, hy + 12 * k, 14 * k, 20 * k, SKIN)
    if back:
        g.ell(hx, hy, 106 * k, 102 * k, HAIR)
        g.ell(hx + 8 * k, hy - 100 * k, 14 * k, 22 * k, HAIR)
        g.line([(hx - 30 * k, hy - 70 * k), (hx, hy - 50 * k), (hx + 34 * k, hy - 74 * k)], HAIR_D, 5 * k)
        do_arms()
        return
    g.ell(hx, hy - 4 * k, 108 * k, 104 * k, HAIR)
    g.ell(hx, hy + 8 * k, 100 * k, 94 * k, SKIN)
    for ox, oy, rx, ry in ((-62, -66, 44, 30), (-18, -82, 46, 32), (34, -76, 46, 32),
                           (74, -52, 36, 30), (-90, -36, 22, 34), (92, -28, 18, 30)):
        g.ell(hx + ox * k, hy + oy * k, rx * k, ry * k, HAIR)
    g.ell(hx + 8 * k, hy - 106 * k, 14 * k, 22 * k, HAIR)
    ey = hy + 8 * k
    for sx in (-1, 1):
        ex = hx + sx * 40 * k
        if eyes == 'blink':
            g.line([(ex - 20 * k, ey), (ex + 20 * k, ey)], '#333', 5 * k)
        elif eyes == 'happy':
            g.arc(ex, ey + 8 * k, 22 * k, 20 * k, 200, 340, '#333', 6 * k)
        else:
            rx, ry, ir = (24, 28, 15) if eyes == 'open' else (31, 38, 21)
            g.ell(ex, ey, rx * k, ry * k, 'white', '#333', 2.5 * k)
            g.ell(ex, ey + 2 * k, ir * k, ir * k, BLUE)
            g.ell(ex, ey + 2 * k, ir * .5 * k, ir * .5 * k, '#12315c')
            g.ell(ex - ir * .35 * k, ey - ir * .35 * k, ir * .28 * k, ir * .28 * k, 'white')
        g.line([(hx + sx * 20 * k, ey - (40 + brow) * k), (hx + sx * 64 * k, ey - (34 + brow) * k)], '#c9a227', 6 * k)
        g.ell(hx + sx * 64 * k, hy + 44 * k, 17 * k, 11 * k, '#ffadad')
    g.ell(hx, hy + 30 * k, 6 * k, 5 * k, '#f0b79a')
    mouth_draw(g, hx, hy + 62 * k, k, mouth)
    do_arms()


def adult(g, fx, fy, sc, kind, mouth='smile', armL=15, armR=15, t=0.0):
    k = sc
    X = lambda v: fx + v * k
    Y = lambda v: fy + v * k
    mom = kind == 'mom'
    cloth = '#e056a0' if mom else '#2f9e8f'
    hair = '#7a4a2b' if mom else '#4a3320'
    mouth = resolve(mouth, t)
    hx, hy = X(0), Y(-545)
    if mom:
        g.ell(hx, hy + 34 * k, 80 * k, 102 * k, hair)
    for sx in (-1, 1):
        g.rect(X(sx * 34 - 22), Y(-210), X(sx * 34 + 22), Y(-15), SKIN if mom else '#3a3f5c', r=10 * k)
        g.ell(X(sx * 38), Y(-12), 34 * k, 17 * k, '#5a3e36')
    if mom:
        g.poly([(X(-62), Y(-470)), (X(62), Y(-470)), (X(100), Y(-190)), (X(-100), Y(-190))], cloth)
        g.rect(X(-66), Y(-480), X(66), Y(-430), cloth, r=22 * k)
    else:
        g.rect(X(-84), Y(-480), X(84), Y(-200), cloth, r=36 * k)
    g.rect(X(-24), Y(-505), X(24), Y(-470), SKIN)
    for sx in (-1, 1):
        g.ell(hx + sx * 62 * k, hy + 6 * k, 9 * k, 14 * k, SKIN)
    g.ell(hx, hy, 63 * k, 68 * k, SKIN)
    g.ell(hx, hy - 42 * k, 68 * k, 36 * k, hair)
    if mom:
        g.ell(hx - 40 * k, hy - 26 * k, 34 * k, 30 * k, hair); g.ell(hx + 44 * k, hy - 22 * k, 30 * k, 28 * k, hair)
    for sx in (-1, 1):
        ex = hx + sx * 25 * k
        g.ell(ex, hy + 4 * k, 12 * k, 14 * k, 'white'); g.ell(ex, hy + 6 * k, 7 * k, 8 * k, '#3b2a20')
        g.line([(ex - 12 * k, hy - 18 * k), (ex + 12 * k, hy - 20 * k)], hair, 5 * k)
        g.ell(hx + sx * 42 * k, hy + 26 * k, 11 * k, 7 * k, '#ffadad')
    mouth_draw(g, hx, hy + 38 * k, k * .8, mouth)
    arms(g, X, Y, k, 70 if mom else 88, -440, 150, armL, armR, cloth, 30, 19)


# ---------------------------------------------------------------- cenario
def sky(g, T):
    g.gradient(0, 900, '#7ccfff', '#dff5ff')
    g.ell(620, 170, 70, 70, '#fff3a8'); g.ell(620, 170, 54, 54, '#ffe066')
    for bx, by, s in ((100, 220, 1.0), (400, 330, .8), (560, 440, .6)):
        cloud(g, (bx + T * 9 * s) % 900 - 120, by, s)


def cloud(g, x, y, s):
    for ox, oy, r in ((0, 0, 44), (46, -14, 54), (96, 0, 42), (48, 16, 46)):
        g.ell(x + ox * s, y + oy * s, r * s, r * .8 * s, 'white')


def grass(g, y):
    g.gradient(y, H, '#79d05a', '#4aa83a')


def heart(g, x, y, s, col):
    g.ell(x - s * .5, y - s * .3, s * .56, s * .56, col); g.ell(x + s * .5, y - s * .3, s * .56, s * .56, col)
    g.poly([(x - s * 1.03, y - s * .05), (x + s * 1.03, y - s * .05), (x, y + s * 1.15)], col)


def star4(g, x, y, r, col, rot=0.0):
    pts = []
    for i in range(8):
        a = rot + i * math.pi / 4
        rr = r if i % 2 == 0 else r * .3
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    g.poly(pts, col)


def room(g, wall, floor, floor_y):
    g.rect(0, 0, W, floor_y, wall); g.gradient(floor_y, H, floor, lerp_col(floor, '#000000', .25))
    g.rect(0, floor_y - 14, W, floor_y, lerp_col(wall, '#000000', .15))


def school(g, shift=0):
    y = 300 + shift
    g.gradient(0, 900, '#7ccfff', '#dff5ff')
    g.rect(0, y + 120, W, y + 560, '#f6b26b')
    g.poly([(-20, y + 130), (360, y - 40), (740, y + 130)], '#c0392b')
    g.rect(210, y + 120, 510, y + 200, '#fff3d6', r=14, ol='#7a4a1b', w=4)
    g.text(360, y + 160, 'ESCOLA', 54, '#c0392b')
    for wx in (40, 130, 520, 610):
        for wy in (y + 250, y + 400):
            g.rect(wx, wy, wx + 70, wy + 100, '#bfe6ff', r=8, ol='#7a4a1b', w=4)
    g.rect(310, y + 330, 410, y + 560, '#6b3f1f', r=10); g.ell(396, y + 450, 6, 6, '#ffd166')
    g.rect(0, y + 560, W, H, '#cfcfcf')
    g.rect(0, y + 540, W, y + 580, '#8d8d8d')


def car(g, x, y):
    g.rect(x, y + 40, x + 270, y + 130, '#e63946', r=26)
    g.poly([(x + 50, y + 42), (x + 90, y - 20), (x + 190, y - 20), (x + 235, y + 42)], '#e63946')
    g.poly([(x + 68, y + 38), (x + 98, y - 8), (x + 135, y - 8), (x + 135, y + 38)], '#bfe6ff')
    g.poly([(x + 145, y + 38), (x + 145, y - 8), (x + 184, y - 8), (x + 218, y + 38)], '#bfe6ff')
    for wx in (x + 62, x + 208):
        g.ell(wx, y + 132, 32, 32, '#222'); g.ell(wx, y + 132, 15, 15, '#ccc')


# ---------------------------------------------------------------- roteiro
COL = {'Lucas': '#ff5c5c', 'Lucas (voz)': '#ff8c42', 'Mamãe': '#e056a0', 'Papai': '#2f9e8f'}
LINES = [
    (0.3, 4.8, 'Lucas', 'Oi, gente! Eu sou o Lucas e eu tenho… quatro anos!'),
    (5.3, 12.8, 'Lucas', 'Eu moro numa casa bem grandona, com meu papai, minha mamãe… e meu cachorro Totó!'),
    (13.3, 22.8, 'Lucas (voz)', 'Minha vida é muito linda! Eu brinco o dia todo, eu como bolo… e todo mundo me ama!'),
    (23.3, 26.0, 'Mamãe', 'Lucas, amanhã é seu primeiro dia de aula!'),
    (26.1, 28.4, 'Lucas', 'Aula? O que é aula?'),
    (28.5, 31.0, 'Papai', 'É onde você vai aprender e fazer amiguinhos!'),
    (31.3, 37.8, 'Lucas', 'Eu vou ser o melhor aluno do mundo inteirooo!'),
    (38.2, 41.0, 'Mamãe', 'Tchau, meu amor! Se divirta!'),
    (41.1, 42.8, 'Papai', 'Seja bonzinho!'),
    (42.9, 45.0, 'Lucas', 'Tchau, mamãe! Tchau, papai!'),
    (46.0, 50.0, 'Lucas', 'Nossa… que grande…'),
    (52.4, 55.0, 'Lucas', '…Uau…!'),
]


def mo(T, who):
    return 'talk' if any(a <= T < b and w == who for a, b, w, _ in LINES) else 'smile'


def wrap(g, txt, size, maxw):
    lines, cur = [], ''
    for w in txt.split():
        test = (cur + ' ' + w).strip()
        if g.tw(test, size) > maxw and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    return lines + [cur]


def caption(g, T):
    for a, b, who, txt in LINES:
        if a <= T < b:
            lines = wrap(g, txt, 40, 570)
            h = len(lines) * 50 + 34
            y1 = 1225; y0 = y1 - h
            g.rect(50, y0, 670, y1, 'white', r=34, ol='#222', w=4)
            for i, l in enumerate(lines):
                g.text(360, y0 + 17 + 25 + i * 50, l, 40, '#222')
            tw = g.tw(who, 30) + 44
            g.rect(70, y0 - 40, 70 + tw, y0 + 8, COL[who], r=24, ol='#222', w=3)
            g.text(70 + tw / 2, y0 - 16, who, 30, 'white')
            return


def ease_pop(x):
    x = min(1, max(0, x))
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1


# ---------------------------------------------------------------- cenas
def s1(g, t, T):
    sky(g, T); grass(g, 880)
    pop = ease_pop(t / .5)
    fingers = 4 if t >= 3.0 else 0
    armR = 125 if t >= 3.0 else 115 + 20 * math.sin(t * 11)
    lucas(g, 360, 940 + math.sin(t * 5) * 3, 1.3 * (.5 + .5 * pop), mo(T, 'Lucas'), armL=20, armR=armR,
          fingers=fingers, t=T)


def s2(g, t, T):
    sky(g, T); grass(g, 880)
    g.rect(40, 520, 440, 890, '#ffd166', r=6, ol='#b8860b', w=4)
    g.poly([(10, 530), (240, 350), (470, 530)], '#d1495b')
    g.rect(190, 700, 290, 890, '#7a4a1b', r=10); g.ell(270, 800, 7, 7, '#ffd166')
    for wx in (70, 330):
        g.rect(wx, 580, wx + 90, 670, '#bfe6ff', r=8, ol='#7a4a1b', w=4); g.line([(wx + 45, 580), (wx + 45, 670)], '#7a4a1b', 4)
    wag = math.sin(t * 14) * 14
    dx, dy = 215, 925
    g.line([(dx - 50, dy - 10), (dx - 78, dy - 50 + wag)], '#b5753a', 14)
    for lx in (-30, 30):
        g.rect(dx + lx - 9, dy + 10, dx + lx + 9, dy + 45, '#9a5f2c', r=6)
    g.ell(dx, dy, 58, 34, '#b5753a'); g.ell(dx + 52, dy - 26, 31, 27, '#b5753a')
    g.ell(dx + 40, dy - 44, 10, 22, '#7a4a1b'); g.ell(dx + 72, dy - 18, 10, 8, '#222')
    g.ell(dx + 58, dy - 32, 5, 5, '#222')
    g.text(dx + 10, dy - 95, 'Totó', 34, '#7a4a1b')
    lucas(g, 585, 960 + math.sin(t * 5) * 3, .92, mo(T, 'Lucas'), armL=100, armR=25, t=T)


def s3(g, t, T):
    i = min(2, int(t / (10 / 3)))
    u = t - i * (10 / 3)
    vo = 'smile' if int(T * 2) % 2 else 'big'
    if i == 0:
        room(g, '#ffe0f0', '#d9a066', 860)
        for wx in (60, 460):
            g.rect(wx, 150, wx + 200, 420, '#bfe6ff', r=12, ol='#fff', w=10)
        cx = 140 + u * 150
        g.rect(cx, 900, cx + 160, 960, '#e63946', r=18); g.rect(cx + 30, 862, cx + 120, 910, '#e63946', r=14)
        for wx in (cx + 34, cx + 126):
            g.ell(wx, 968, 24, 24, '#222'); g.ell(wx, 968, 10, 10, '#ccc')
        lucas(g, 500, 1000 + math.sin(u * 8) * 4, 1.15, vo, armL=60, armR=120, t=T)
    elif i == 1:
        room(g, '#fff1c9', '#c68e5b', 860)
        lucas(g, 360, 960, 1.15, vo, eyes='happy', armL=135 + 10 * math.sin(u * 9), armR=135 - 10 * math.sin(u * 9), t=T)
        g.rect(60, 800, 660, 850, '#a0693a', r=14); g.rect(110, 850, 150, 1100, '#8a5a2e'); g.rect(570, 850, 610, 1100, '#8a5a2e')
        g.rect(240, 730, 480, 800, '#ff9ecb', r=14); g.rect(270, 690, 450, 735, '#ffffff', r=12)
        g.rect(352, 640, 368, 692, '#4dabf7', r=4)
        g.ell(360, 625 + math.sin(u * 20) * 2, 11, 20, '#ffb703')
        for ox in (-150, -50, 50, 150):
            g.ell(360 + ox, 737, 9, 9, '#e63946')
    else:
        sky(g, T); grass(g, 880)
        jump = abs(math.sin(u * 4.2)) * 150
        lucas(g, 360, 960 - jump, 1.15, 'big', eyes='happy', armL=140, armR=140, t=T)
        cols = ['#ff6b6b', '#ffd43b', '#51cf66', '#339af0', '#cc5de8']
        for n in range(26):
            px = (n * 97) % 700 + 10; py = ((n * 61 + u * 220) % 900)
            g.rect(px, py, px + 14, py + 26, cols[n % 5], r=3)
    for n in range(5):
        hy = 1150 - ((T * 60 + n * 230) % 1200) + 120
        heart(g, 70 + n * 140 + math.sin(T * 2 + n) * 20, hy, 22 + n % 3 * 6, ['#ff6b81', '#ff8fab', '#ff4d6d'][n % 3])


def s4(g, t, T):
    room(g, '#ffe9c7', '#c68e5b', 880)
    g.rect(50, 170, 260, 430, '#bfe6ff', r=12, ol='#fff', w=12); g.line([(155, 170), (155, 430)], '#fff', 8)
    g.rect(470, 200, 650, 340, '#fff', r=8, ol='#8a5a2e', w=8); g.ell(560, 270, 40, 40, '#ffd43b')
    g.rect(170, 700, 550, 890, '#8e6bbf', r=40); g.rect(150, 760, 200, 890, '#7a58ad', r=20); g.rect(520, 760, 570, 890, '#7a58ad', r=20)
    mom_talk = 23.3 <= T < 26.0
    dad_talk = 28.5 <= T < 31.0
    lu_talk = 26.1 <= T < 28.4
    adult(g, 120, 1060, .95, 'mom', mo(T, 'Mamãe'), armL=25, armR=125 + 20 * math.sin(t * 9) if mom_talk else 25, t=T)
    adult(g, 600, 1060, .95, 'dad', mo(T, 'Papai'), armL=125 + 20 * math.sin(t * 9) if dad_talk else 25, armR=25, t=T)
    lucas(g, 360, 1050, 1.0, 'o' if lu_talk else 'smile', eyes='wow' if lu_talk else 'auto',
          brow=10 if lu_talk else 0, armL=20, armR=20 if not lu_talk else 100, t=T)


def s5(g, t, T):
    room(g, '#cfe9ff', '#c9a074', 900)
    g.rect(40, 150, 260, 420, '#fff6c9', r=12, ol='#fff', w=12); g.ell(150, 260, 54, 54, '#ffe066')
    for a in range(0, 360, 30):
        r = math.radians(a + t * 20)
        g.line([(150 + math.cos(r) * 70, 260 + math.sin(r) * 70), (150 + math.cos(r) * 96, 260 + math.sin(r) * 96)], '#ffe066', 6)
    g.rect(470, 720, 700, 900, '#ff9f43', r=14); g.rect(470, 700, 700, 750, '#fff', r=14)
    jump = abs(math.sin(t * 5)) * 45
    lucas(g, 330, 1030 - jump, 1.25, mo(T, 'Lucas'), eyes='happy', armL=140, armR=140,
          shirt='#f4f4f4', pants='#27408b', pack='#ff9f1c', t=T)
    for n in range(7):
        star4(g, 100 + n * 90, 600 + math.sin(t * 3 + n) * 40, 12 + n % 3 * 5, '#ffd43b', t * 2 + n)


def s6(g, t, T):
    school(g)
    car_x = -300 + 340 * ease_out(t / 1.5)
    car(g, car_x, 890)
    waving = t > 1.6
    adult(g, 390, 1130, .78, 'mom', mo(T, 'Mamãe'), armL=20, armR=(125 + 20 * math.sin(t * 11)) if waving else 20, t=T)
    adult(g, 500, 1130, .78, 'dad', mo(T, 'Papai'), armL=20, armR=(125 + 20 * math.sin(t * 11 + 1)) if waving else 20, t=T)
    lw = 125 + 20 * math.sin(t * 12) if t > 4.2 else 20
    lucas(g, 625, 1110, .9, mo(T, 'Lucas'), armL=lw, armR=20, shirt='#f4f4f4', pants='#27408b', pack='#ff9f1c', t=T)


def ease_out(x):
    x = min(1, max(0, x))
    return 1 - (1 - x) ** 3


def s7(g, t, T):
    zoom = 1 + .22 * (t / 7)
    school(g, shift=-40 * (t / 7))
    for bx in range(10, W, 64):
        g.rect(bx, 560, bx + 12, H, '#2b2d42')
    g.rect(0, 640, W, 668, '#2b2d42'); g.rect(0, 980, W, 1008, '#2b2d42')
    lucas(g, 360, 1110 + 30 * (t / 7), 1.05 * zoom, 'smile', back=True, shirt='#f4f4f4', pants='#27408b', pack='#ff9f1c', t=T)


def s8(g, t, T):
    if t >= 4.3:
        g.rect(0, 0, W, H, '#000')
        a = min(1, (t - 4.5) / .6)
        c = lerp_col('#000000', '#ffffff', max(0, a))
        g.text(360, 600, 'CONTINUA…', 92, c)
        g.text(360, 720, 'Episódio 2 em breve', 40, lerp_col('#000000', '#ffd43b', max(0, a)))
        return
    g.gradient(0, H, '#fff3b0', '#ff8fab')
    for n in range(14):
        r = math.radians(n * (360 / 14) + t * 14)
        g.poly([(360, 560), (360 + math.cos(r) * 1400, 560 + math.sin(r) * 1400),
                (360 + math.cos(r + .12) * 1400, 560 + math.sin(r + .12) * 1400)], '#ffe27a')
    pop = ease_pop(t / .45)
    lucas(g, 360, 1500, 3.0 * (.55 + .45 * pop), 'o' if t < 1.6 else 'big', eyes='wow', brow=14, armL=20, armR=20, t=T)
    for n in range(10):
        a = n * .63 + t * .8
        star4(g, 360 + math.cos(a) * (270 + 40 * math.sin(t * 3 + n)), 520 + math.sin(a) * 330, 22 + (n % 3) * 9, '#ffffff', t * 2 + n)


SCENES = [(0, 5, s1), (5, 13, s2), (13, 23, s3), (23, 31, s4), (31, 38, s5), (38, 45, s6), (45, 52, s7), (52, 58.01, s8)]


def render(T):
    g = G()
    for a, b, fn in SCENES:
        if a <= T < b:
            fn(g, T - a, T)
            break
    if T < 52.3:
        g.rect(22, 26, 330, 84, '#222', r=28)
        g.text(176, 55, 'LUCAS • EP. 1', 30, 'white')
    caption(g, T)
    return g.out()


# ---------------------------------------------------------------- audio
VOICES = {  # voz do espeak-ng (pt-br) + tom (-p) por personagem
    'Lucas': ('pt-br+f5', 99, 165), 'Lucas (voz)': ('pt-br+f5', 99, 165),
    'Mamãe': ('pt-br+f2', 62, 155), 'Papai': ('pt-br+m3', 28, 150),
}


def voice(txt, who, max_dur, sr):
    import tempfile
    v, pitch, speed = VOICES[who]
    txt = txt.replace('…', ', ')
    for _ in range(6):
        with tempfile.NamedTemporaryFile(suffix='.wav') as f:
            subprocess.run(['espeak-ng', '-v', v, '-p', str(pitch), '-s', str(speed), '-g', '4', '-w', f.name, txt], check=True)
            with wave.open(f.name) as w:
                rate, raw = w.getframerate(), w.readframes(w.getnframes())
        x = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768
        if len(x) / rate <= max_dur:
            break
        speed = int(speed * 1.12)
    t_new = np.arange(int(len(x) / rate * sr)) / sr
    x = np.interp(t_new, np.arange(len(x)) / rate, x)
    return x / max(1e-6, np.abs(x).max()) * .9


def make_audio(path, sr=44100):
    n = int(DUR * sr)
    buf = np.zeros(n, dtype=np.float64)

    def add(t0, sig, gain=1.0):
        i = int(t0 * sr)
        if i >= n: return
        j = min(n, i + len(sig))
        buf[i:j] += sig[:j - i] * gain

    def pluck(f, d=.5):
        x = np.arange(int(d * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + .4 * np.sin(4 * np.pi * f * x) + .15 * np.sin(6 * np.pi * f * x)) * np.exp(-x * 7)

    def bell(f, d=2.0):
        x = np.arange(int(d * sr)) / sr
        return (np.sin(2 * np.pi * f * x) * np.exp(-x * 2.6) + .35 * np.sin(2 * np.pi * f * 2.76 * x) * np.exp(-x * 5)
                + .2 * np.sin(2 * np.pi * f * 5.4 * x) * np.exp(-x * 8))

    chords = [(261.63, 329.63, 392.0), (220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    step = 60 / 112 / 2
    rng = np.random.default_rng(1)
    pattern = [0, 1, 2, 1, 2, 1, 0, 1]
    for i in range(int(52 / step)):
        t0 = i * step
        ch = chords[(i // 8) % 4]
        gain = .5 if t0 >= 45 else 1.0
        add(t0, pluck(ch[pattern[i % 8]] * 2, .45), .28 * gain)
        if i % 4 == 0: add(t0, pluck(ch[0] / 2, .7), .5 * gain)
        if i % 2 == 1 and t0 < 45:
            add(t0, rng.standard_normal(int(.03 * sr)) * np.exp(-np.arange(int(.03 * sr)) / sr * 140), .06)
    for k, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
        add(52.35 + k * .11, bell(f), .22)
    add(54.2, bell(1568.0, 2.5), .12)
    buf *= .35  # musica baixa, a voz fica na frente
    for a0, b0, who, txt in LINES:
        v = voice(txt, who, b0 - a0 - .15, sr)
        add(a0 + .1, v, 1.0)
    buf /= max(1e-6, np.abs(buf).max()) / .85
    fade = int(.6 * sr)
    buf[-fade:] *= np.linspace(1, 0, fade)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((buf * 32767).astype('<i2').tobytes())


def _frame(i):
    return render(i / FPS).convert('RGB').tobytes()


def main():
    mode, out = sys.argv[1], sys.argv[2]
    if mode == 'preview':
        ts = [3.5, 9, 15, 20, 21.5, 27, 34, 42, 48.5, 53.5]
        sheet = Image.new('RGB', (5 * 288, 2 * 512), 'white')
        for n, T in enumerate(ts):
            sheet.paste(render(T).resize((288, 512), Image.LANCZOS), ((n % 5) * 288, (n // 5) * 512))
        sheet.save(out)
        return
    wav = out.rsplit('.', 1)[0] + '.wav'
    make_audio(wav)
    total = int(DUR * FPS)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out],
                          stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as p:
        for fr in p.imap(_frame, range(total), chunksize=4):
            ff.stdin.write(fr)
    ff.stdin.close(); ff.wait()
    os.remove(wav)


if __name__ == '__main__':
    main()
