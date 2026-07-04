"""LightGaussian degree 3→2 축소 및 zero-padding 처리 시각화"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sh_degree_padding.png')

BG     = '#0d0d0d'
C_R    = '#d94040'; C_G = '#40b840'; C_B = '#4080d9'
C_ZERO = '#252525'; C_PAD = '#181818'

fig = plt.figure(figsize=(16, 12))
fig.patch.set_facecolor(BG)

def rect(ax, x, y, w, h, fc, ec='#555', txt='', fs=8, bold=False):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle='round,pad=0.04',
        fc=fc, ec=ec, lw=0.8, zorder=2))
    if txt:
        ax.text(x+w/2, y+h/2, txt, ha='center', va='center',
                fontsize=fs, color='white', fontweight='bold' if bold else 'normal', zorder=3)

ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
ax.set_facecolor('#111'); ax.set_xlim(0, 20); ax.set_ylim(0, 19); ax.axis('off')
ax.text(10, 18.5, 'LightGaussian degree 3→2 축소와 .unitygs zero-padding 처리',
        ha='center', fontsize=13, color='white', fontweight='bold')

cols = [
    (2.5,  [0.7, 1.9, 3.1],  1.0, 'degree 3  PLY',  '(원본 3DGS, f_rest 45개)',            '#2a3a5a'),
    (8.5,  [6.7, 7.9, 9.1],  1.0, 'degree 2  PLY',  '(LightGaussian 압축 후, f_rest 24개)', '#3a2a4a'),
    (15.0, [13.2,14.4,15.6], 1.0, '.unitygs  SH',   '(48 floats = 16 × float3)',            '#1a4a1a'),
]
CH_COLORS = [C_R, C_G, C_B]
CH_NAMES  = ['R', 'G', 'B']

for (cx, xs, cw, title, sub, hdr_fc) in cols:
    ax.add_patch(mpatches.FancyBboxPatch(
        (xs[0]-0.1, 17.4), xs[2]+cw+0.1-xs[0]+0.1, 0.7,
        boxstyle='round,pad=0.08', fc=hdr_fc, ec='#555', lw=1.0, zorder=2))
    ax.text(cx, 17.75, title, ha='center', fontsize=10.5, color='white', fontweight='bold', zorder=3)
    ax.text(cx, 17.35, sub,   ha='center', fontsize=8,    color='#aaa',  zorder=3)
    for x, ch, col in zip(xs, CH_NAMES, CH_COLORS):
        ax.text(x+cw/2, 17.0, ch, ha='center', fontsize=9, color=col, fontweight='bold')

for i in range(16):
    ax.text(0.35, 16.3 - i*1.0 + 0.35,
            f'coeff {i}' if i < 15 else 'pad', ha='right', fontsize=7.5, color='#666')

# degree 3 PLY
_, xs3, cw, *_ = cols[0]
for i in range(15):
    y = 16.3 - i * 1.0
    for x, col, ch in zip(xs3, CH_COLORS, CH_NAMES):
        rect(ax, x, y, cw, 0.75, col+'44', ec=col, txt=ch+str(i), fs=8, bold=True)
for x in xs3:
    rect(ax, x, 16.3 - 15*1.0, cw, 0.75, C_PAD, ec='#333', txt='—', fs=8)
ax.text(cols[0][0], 16.3 - 15*1.0 - 0.5, '총 45개 (degree 3)', ha='center', fontsize=9,
        color='#7ab8e8', bbox=dict(fc='#1a2a3a', ec='#4a6a8a', boxstyle='round,pad=0.3'))

# degree 2 PLY
_, xs2, cw, *_ = cols[1]
for i in range(8):
    y = 16.3 - i * 1.0
    for x, col, ch in zip(xs2, CH_COLORS, CH_NAMES):
        rect(ax, x, y, cw, 0.75, col+'44', ec=col, txt=ch+str(i), fs=8, bold=True)
for i in range(8, 15):
    y = 16.3 - i * 1.0
    for x in xs2:
        rect(ax, x, y, cw, 0.75, '#330000', ec='#882222', txt='없음', fs=7)
for x in xs2:
    rect(ax, x, 16.3 - 15*1.0, cw, 0.75, C_PAD, ec='#333', txt='—', fs=8)
ax.text(cols[1][0], 16.3 - 15*1.0 - 0.5, '총 24개 (degree 2)', ha='center', fontsize=9,
        color='#c09fe0', bbox=dict(fc='#2a1a3a', ec='#7a4a9a', boxstyle='round,pad=0.3'))
ax.text(8.5, 16.3 - 14.7*1.0 - 1.2,
        '원본 Unity 에디터 변환기:\n"f_rest 45개" 고정 가정 → 크래시 또는 오류',
        ha='center', fontsize=8.5, color='#f08080',
        bbox=dict(fc='#330000', ec='#882222', boxstyle='round,pad=0.4'))

# .unitygs
_, xsU, cw, *_ = cols[2]
for i in range(8):
    y = 16.3 - i * 1.0
    for x, col, ch in zip(xsU, CH_COLORS, CH_NAMES):
        rect(ax, x, y, cw, 0.75, col+'55', ec=col, txt=ch+str(i), fs=8, bold=True)
for i in range(8, 15):
    y = 16.3 - i * 1.0
    for x in xsU:
        rect(ax, x, y, cw, 0.75, C_ZERO, ec='#444', txt='0', fs=8)
    ax.text(xsU[2]+cw+0.15, y+0.35, 'zero-padding', ha='left', fontsize=7.5, color='#606060')
for x in xsU:
    rect(ax, x, 16.3 - 15*1.0, cw, 0.75, C_PAD, ec='#333', txt='PAD', fs=7.5)
ax.text(xsU[2]+cw+0.15, 16.3 - 15*1.0 + 0.35, 'align padding', ha='left', fontsize=7.5, color='#505050')
ax.text(cols[2][0], 16.3 - 15*1.0 - 0.5, '항상 48 floats (고정 크기)', ha='center', fontsize=9,
        color='#7fe87a', bbox=dict(fc='#1a3a1a', ec='#4a8a4a', boxstyle='round,pad=0.3'))

# 화살표
for row in range(8):
    y_mid = 16.3 - row * 1.0 + 0.375
    ax.annotate('', xy=(xsU[0]-0.1, y_mid), xytext=(xs2[2]+cw+0.05, y_mid),
                arrowprops=dict(arrowstyle='->', color='#7fe87a', lw=1.3))
for row in range(8, 15):
    y_mid = 16.3 - row * 1.0 + 0.375
    ax.annotate('', xy=(xsU[0]-0.1, y_mid), xytext=(xs2[2]+cw+0.05, y_mid),
                arrowprops=dict(arrowstyle='->', color='#888833', lw=1.3, ls='dashed'))
    ax.text((xs2[2]+cw + xsU[0]-0.1)/2, y_mid+0.15, '0으로 채움',
            ha='center', fontsize=7, color='#888833')

ax.annotate('', xy=(xs2[0]-0.15, 16.3 - 3.5*1.0), xytext=(xs3[2]+cw+0.1, 16.3 - 3.5*1.0),
            arrowprops=dict(arrowstyle='->', color='#c09fe0', lw=2.0))
ax.text((xs3[2]+cw + xs2[0]-0.15)/2, 16.3 - 3.5*1.0 + 0.3,
        'LightGaussian 압축\ncoeff 8~14 제거', ha='center', fontsize=8.5,
        color='#c09fe0', fontweight='bold')
ax.annotate('', xy=(xs2[0]-0.15, 16.3 - 10.5*1.0), xytext=(xs3[2]+cw+0.1, 16.3 - 10.5*1.0),
            arrowprops=dict(arrowstyle='->', color='#f08080', lw=1.5, ls='dashed'))
ax.text((xs3[2]+cw + xs2[0]-0.15)/2, 16.3 - 10.5*1.0 + 0.3,
        '제거됨', ha='center', fontsize=8.5, color='#f08080')

items = [
    mpatches.Patch(fc=C_R+'44', ec=C_R,    label='R 채널'),
    mpatches.Patch(fc=C_G+'44', ec=C_G,    label='G 채널'),
    mpatches.Patch(fc=C_B+'44', ec=C_B,    label='B 채널'),
    mpatches.Patch(fc='#330000', ec='#882222', label='degree 2에 없음'),
    mpatches.Patch(fc=C_ZERO,   ec='#444', label='zero-padding'),
    mpatches.Patch(fc=C_PAD,    ec='#333', label='alignment pad'),
]
ax.legend(handles=items, loc='lower center', ncol=6, fontsize=9,
          facecolor='#1a1a1a', labelcolor='white', framealpha=0.9,
          bbox_to_anchor=(0.5, 0.0))

plt.savefig(OUT, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved:', OUT)
