"""SH 채널 순차 배열 ↔ 인터리브 불일치 시각화"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sh_layout_mismatch.png')

BG      = '#0d0d0d'
C_R     = '#d94040'; C_G = '#40b840'; C_B = '#4080d9'
C_WRONG = '#662222'

fig = plt.figure(figsize=(16, 10))
fig.patch.set_facecolor(BG)

def rect(ax, x, y, w, h, fc, ec='#555', txt='', fs=8, bold=False):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle='round,pad=0.04',
        fc=fc, ec=ec, lw=0.8, zorder=2))
    if txt:
        ax.text(x+w/2, y+h/2, txt, ha='center', va='center',
                fontsize=fs, color='white', fontweight='bold' if bold else 'normal', zorder=3)

# ── 섹션 1: PLY 메모리 레이아웃 ──────────────────────────────────────────
ax1 = fig.add_axes([0.03, 0.72, 0.94, 0.24])
ax1.set_facecolor('#111'); ax1.set_xlim(0, 24.4); ax1.set_ylim(0, 3); ax1.axis('off')
ax1.text(12.2, 2.7, 'PLY  f_rest  메모리 레이아웃 (degree 2 기준, 채널당 8개 계수, 총 24개)',
         ha='center', fontsize=11, color='white', fontweight='bold')

COLORS = [C_R]*8 + [C_G]*8 + [C_B]*8
LABELS = [f'R{i}' for i in range(8)] + [f'G{i}' for i in range(8)] + [f'B{i}' for i in range(8)]

for idx in range(24):
    x = idx + 0.2
    rect(ax1, x, 1.0, 0.85, 0.9, COLORS[idx], ec='#333', txt=LABELS[idx], fs=8, bold=True)
    ax1.text(x+0.43, 0.8, str(idx), ha='center', fontsize=6.5, color='#888')

for x0, x1, col, lbl in [
    (0.2,  8.05,  C_R+'aa', 'R 채널 (f_rest 0~7)'),
    (8.2,  16.05, C_G+'aa', 'G 채널 (f_rest 8~15)'),
    (16.2, 24.05, C_B+'aa', 'B 채널 (f_rest 16~23)'),
]:
    ax1.annotate('', xy=(x1, 0.35), xytext=(x0, 0.35),
                 arrowprops=dict(arrowstyle='-', color=col, lw=2))
    ax1.plot([x0, x0], [0.35, 0.5], color=col, lw=1.5)
    ax1.plot([x1, x1], [0.35, 0.5], color=col, lw=1.5)
    ax1.text((x0+x1)/2, 0.15, lbl, ha='center', fontsize=8.5, color=col, fontweight='bold')

# ── 섹션 2: WRONG vs CORRECT ─────────────────────────────────────────────
ax2 = fig.add_axes([0.03, 0.04, 0.94, 0.64])
ax2.set_facecolor('#111'); ax2.set_xlim(0, 24); ax2.set_ylim(0, 8.5); ax2.axis('off')

ax2.text(4.5, 8.1, 'WRONG  —  naive copy  (sh[i] = f_rest[i])',
         ha='center', fontsize=11, color='#f07070', fontweight='bold')
ax2.text(4.5, 7.65, 'f_rest 인덱스 순서 그대로 복사',
         ha='center', fontsize=9, color='#aaa', style='italic')
ax2.text(17.5, 8.1, 'CORRECT  —  채널 분리 후 계수별 교차 배치',
         ha='center', fontsize=11, color='#70f070', fontweight='bold')
ax2.text(17.5, 7.65, 'sh[i×3+0]=R_i,  sh[i×3+1]=G_i,  sh[i×3+2]=B_i  (계수별 RGB 교차 배치)',
         ha='center', fontsize=9, color='#aaa', style='italic')

ax2.plot([11.5, 11.5], [0.2, 8.4], color='#333', lw=1.5, ls='--')

# R/G/B 컬럼 헤더
for base_x in [1.0, 13.5]:
    for ci, (ch, col) in enumerate([('R', C_R), ('G', C_G), ('B', C_B)]):
        ax2.text(base_x + ci*3.0 + 1.1, 7.1, ch,
                 ha='center', fontsize=10, color=col, fontweight='bold')
    ax2.text(base_x - 0.1, 7.1, 'float3', ha='right', fontsize=8, color='#666')

# 채널 인덱스로 실제 채널 배경/테두리 색상 반환
def ch_color_dark(label_idx):
    if label_idx < 8:   return '#8b2020', C_R   # R: 어두운 빨강 배경, C_R 테두리
    if label_idx < 16:  return '#207820', C_G   # G: 어두운 초록 배경, C_G 테두리
    return                     '#204580', C_B   # B: 어두운 파랑 배경, C_B 테두리

# WRONG: 나이브 복사 시 float3[i] = (R_{3i}, R_{3i+1}, R_{3i+2})
for ri in range(8):
    base = ri * 3
    y = 6.2 - ri * 0.77
    ax2.text(0.95, y+0.28, f'{ri}', ha='right', fontsize=7.5, color='#666')
    for ci in range(3):
        idx = base + ci
        fc, ec = ch_color_dark(idx)
        rect(ax2, 1.0 + ci*3.0, y, 2.6, 0.65, fc, ec=ec,
             txt=LABELS[idx], fs=8.5, bold=True)
    ax2.text(10.2, y+0.28, 'X', ha='center', fontsize=11, color='#f04040', fontweight='bold')

# CORRECT: float3[i] = (R_i, G_i, B_i)
for ri in range(8):
    y = 6.2 - ri * 0.77
    ax2.text(13.4, y+0.28, f'{ri}', ha='right', fontsize=7.5, color='#666')
    for ci, (ch, col) in enumerate([(f'R{ri}', C_R), (f'G{ri}', C_G), (f'B{ri}', C_B)]):
        rect(ax2, 13.5 + ci*3.0, y, 2.6, 0.65, col+'55', ec=col,
             txt=ch, fs=8.5, bold=True)
    ax2.text(22.7, y+0.28, 'O', ha='center', fontsize=11, color='#40f040', fontweight='bold')


plt.savefig(OUT, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved:', OUT)
