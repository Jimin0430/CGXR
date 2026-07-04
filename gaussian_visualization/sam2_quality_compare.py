"""SAM2 적용 여부에 따른 3DGS 학습 품질 비교 시각화"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plyfile import PlyData

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sam2_quality_compare.png')

SAM2_PLY   = r'D:\JM\cgxr\CGXR\server\workdir\ebc97859-33f2-493f-8727-50bb3864a5fd\output\point_cloud\iteration_30000\point_cloud.ply'
NOSAM2_PLY = r'D:\JM\cgxr\CGXR\server\workdir\nosam2_compare\output\point_cloud\iteration_30000\point_cloud.ply'

def load_xyz(path):
    v = PlyData.read(path)['vertex']
    return np.column_stack([v['x'], v['y'], v['z']]).astype(np.float32)

sam2   = load_xyz(SAM2_PLY)
nosam2 = load_xyz(NOSAM2_PLY)

fig, axes = plt.subplots(2, 1, figsize=(9, 14))
fig.patch.set_facecolor('black')

# ── Panel 1: Test PSNR 비교 ─────────────────────────────────────────────
iters        = [7000, 30000]
psnr_sam2   = [28.78, 29.11]
psnr_nosam2 = [27.67, 28.25]
x = np.arange(len(iters)); w = 0.35

ax = axes[0]
ax.set_facecolor('#111')
b1 = ax.bar(x - w/2, psnr_sam2,   w, label='SAM2 적용',  color='steelblue', alpha=0.9)
b2 = ax.bar(x + w/2, psnr_nosam2, w, label='SAM2 미적용', color='tomato',    alpha=0.9)
ax.set_xticks(x)
ax.set_xticklabels(['Iter 7,000', 'Iter 30,000'], color='white', fontsize=18)
ax.set_ylabel('PSNR (dB)', color='white', fontsize=18)
ax.set_title('Test PSNR 비교', color='white', fontsize=24)
ax.set_ylim(26, 31)
ax.legend(facecolor='#222', labelcolor='white', fontsize=18)
ax.tick_params(colors='white', labelsize=16)
for s in ['bottom', 'left']: ax.spines[s].set_color('#444')
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
for bar in list(b1) + list(b2):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'{bar.get_height():.2f}', ha='center', va='bottom',
            color='white', fontsize=18)
ax.annotate(f'+{psnr_sam2[1]-psnr_nosam2[1]:.2f} dB',
            xy=(1, psnr_sam2[1] + 0.45),
            color='#7fff7f', fontsize=22, ha='center', fontweight='bold')

# ── Panel 2: Gaussian 분포 오버레이 ─────────────────────────────────────
ax2 = axes[1]
ax2.set_facecolor('black')
cx = np.median(sam2[:, 0]); cy = np.median(sam2[:, 1])
r  = max(np.percentile(np.abs(sam2[:, 0] - cx), 98),
         np.percentile(np.abs(sam2[:, 1] - cy), 98)) * 1.5
ax2.scatter(sam2[:,0],   sam2[:,1],   s=0.3,  alpha=0.5, c='steelblue',
            label=f'SAM2 적용 ({len(sam2):,}개)',    rasterized=True)
ax2.scatter(nosam2[:,0], nosam2[:,1], s=0.15, alpha=0.3, c='tomato',
            label=f'SAM2 미적용 ({len(nosam2):,}개)', rasterized=True)
ax2.set_xlim(cx - r, cx + r); ax2.set_ylim(cy + r, cy - r)
ax2.set_title('Gaussian 분포 오버레이 (XY, 위에서 본 뷰)', color='white', fontsize=24)
ax2.set_xlabel('X', color='#aaa', fontsize=18)
ax2.set_ylabel('Y', color='#aaa', fontsize=18)
ax2.tick_params(colors='#666', labelsize=16)
for s in ax2.spines.values(): s.set_color('#333')
ax2.legend(facecolor='#222', labelcolor='white', markerscale=8,
           fontsize=18, loc='upper right')

fig.suptitle('SAM2 배경 제거 적용 여부에 따른\n3DGS 학습 품질 비교',
             fontsize=26, color='white', y=1.01)
plt.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches='tight', facecolor='black')
plt.close()
print('saved:', OUT)
