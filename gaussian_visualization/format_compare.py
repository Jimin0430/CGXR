"""PLY vs .unitygs 포맷 구조 비교 시각화"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'format_compare.png')

BG     = '#0d0d0d'
PANEL  = '#131313'
C_POS  = '#4a90d9'; C_ROT = '#e07030'; C_SCL = '#50b060'
C_COL  = '#c050c0'; C_OPAC = '#c0c050'; C_SH = '#50c0c0'
C_HDR  = '#3a3a3a'; C_ARROW = '#ffdd44'

fig, ax = plt.subplots(figsize=(16, 12))
fig.patch.set_facecolor(BG)
ax.set_facecolor(PANEL); ax.set_xlim(0, 16); ax.set_ylim(0, 13); ax.axis('off')
ax.text(8, 12.5, 'PLY (3DGS)  vs  .unitygs 포맷 구조 비교',
        ha='center', va='center', fontsize=14, color='white', fontweight='bold')

LX, RX, W = 1.0, 9.5, 5.8

def block(x, y, w, h, fc, label, sublabel='', fs=9.5):
    ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h,
        boxstyle='round,pad=0.06', fc=fc, ec='#555', lw=0.9, zorder=2))
    ax.text(x+w/2, y+h/2+(0.13 if sublabel else 0), label,
            ha='center', va='center', fontsize=fs, color='white', fontweight='bold', zorder=3)
    if sublabel:
        ax.text(x+w/2, y+h/2-0.18, sublabel,
                ha='center', va='center', fontsize=7.5, color='#bbb', zorder=3)

def arrow(x1, y, x2, label=''):
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='->', color=C_ARROW, lw=1.6))
    if label:
        ax.text((x1+x2)/2, y+0.15, label, ha='center', va='bottom',
                fontsize=7.5, color=C_ARROW)

ax.text(LX+W/2, 12.0, 'PLY  (3DGS 학습 출력)',   ha='center', fontsize=11, color='#7ab8e8', fontweight='bold')
ax.text(RX+W/2, 12.0, '.unitygs  (Unity 런타임)', ha='center', fontsize=11, color='#7fe87a', fontweight='bold')

rows = [
    (11.3, 0.55, 'PLY 텍스트 헤더',     'ply / format / element …',        '바이너리 헤더 12 B',  'magic | version | count',          '구조 고정',             C_HDR),
    (10.5, 0.55, 'x, y, z',            'float32 × 3  (위치)',              'Position',           'float32[N][3]',                     '동일',                  C_POS),
    (9.7,  0.55, 'scale_0~2',          'float32 × 3  (log 공간)',          'Scale',              'float32[N][3]  (선형)',              'exp(scale)',            C_SCL),
    (8.9,  0.55, 'rot_0~3',            'float32 × 4  (w x y z)',           'Rotation',           'float32[N][4]  (x y z w)',          'wxyz → xyzw',           C_ROT),
    (7.9,  0.75, 'f_dc_0~2\n+ opacity','DC SH + logit opacity',            'Color (RGBA)',       'float32[N][4]  0~1',                'f_dc×SH_C0+0.5\nsigmoid(opacity)', C_COL),
    (7.0,  0.55, '(없음)',             '',                                  'hasSH',              'bool  1 byte',                      'SH 포함 여부 플래그',   C_OPAC),
    (5.6,  1.05, 'f_rest_0~44',        'float32 × 45\n채널별 순차 (R…R G…G B…B)',
                                                                            'SH Coefficients',   'float32[N][48]\nfloat3 인터리브 (RGB RGB…)\n+ zero-padding',
                                                                                                  'SH 재배열\n+0 padding',             C_SH),
    (4.7,  0.55, '(저장 순서 임의)',   'PLY 학습 완료 순서',               '(Morton 3D 정렬)',    '공간 Z-curve 순서',                 'Morton sort',           '#aaaaaa'),
]

for (yc, h, pl, ps, ul, us, albl, fc) in rows:
    y0 = yc - h/2
    block(LX, y0, W, h, fc+'22', pl, ps)
    block(RX, y0, W, h, fc+'44', ul, us)
    arrow(LX+W+0.05, yc, RX-0.05, albl)

ax.plot([LX, LX+W], [4.15, 4.15], color='#444', lw=0.8, ls='--')
ax.plot([RX, RX+W], [4.15, 4.15], color='#444', lw=0.8, ls='--')
ax.text(LX+W/2, 3.75, '17.2 MB  (ebc97859 기준)', ha='center', fontsize=10, color='#f08080', fontweight='bold')
ax.text(RX+W/2, 3.75, '5.8 MB', ha='center', fontsize=10, color='#80f080', fontweight='bold')
ax.annotate('', xy=(RX+W/2, 3.45), xytext=(LX+W/2, 3.45),
            arrowprops=dict(arrowstyle='->', color=C_ARROW, lw=2.0))
ax.text(8.0, 3.6, '66% 감소  (LG 압축 포함)', ha='center', fontsize=9, color=C_ARROW, fontweight='bold')

legend = [
    mpatches.Patch(fc=C_POS+'44', ec='#555', label='위치 (Position)'),
    mpatches.Patch(fc=C_SCL+'44', ec='#555', label='스케일 (Scale)'),
    mpatches.Patch(fc=C_ROT+'44', ec='#555', label='회전 (Rotation)'),
    mpatches.Patch(fc=C_COL+'44', ec='#555', label='색상 / 불투명도'),
    mpatches.Patch(fc=C_SH+'44',  ec='#555', label='SH 계수'),
    mpatches.Patch(fc=C_HDR+'44', ec='#555', label='헤더 / 메타'),
]
ax.legend(handles=legend, loc='lower center', ncol=6, fontsize=8.5,
          facecolor='#1a1a1a', labelcolor='white', framealpha=0.9,
          bbox_to_anchor=(0.5, 0.0))

plt.savefig(OUT, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved:', OUT)
