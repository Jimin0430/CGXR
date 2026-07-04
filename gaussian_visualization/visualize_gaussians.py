"""
Gaussian 중심점 분포 시각화 스크립트
압축 전(3DGS) vs 압축 후(LightGaussian) 비교
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plyfile import PlyData

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

RAW_PATH  = r'D:\JM\cgxr\CGXR\server\workdir\ebc97859-33f2-493f-8727-50bb3864a5fd\output\point_cloud\iteration_30000\point_cloud.ply'
COMP_PATH = r'D:\JM\cgxr\CGXR\server\workdir\ebc97859-33f2-493f-8727-50bb3864a5fd\lg_output\stage3_quantized\point_cloud.ply'
OUT_COLOR = r'D:\JM\cgxr\CGXR\gaussian_visualization\gaussian_compare.png'
OUT_WHITE = r'D:\JM\cgxr\CGXR\gaussian_visualization\gaussian_compare_white.png'


def load_xyz(path):
    v = PlyData.read(path)['vertex']
    return np.column_stack([v['x'], v['y'], v['z']]).astype(np.float32)


def get_lim(pts, axis, pad=0.3):
    return np.percentile(pts[:, axis], 1) - pad, np.percentile(pts[:, axis], 99) + pad


def make_plot(raw, comp, same_color=False):
    views = [
        ('앞에서 본 뷰', 0, 1, 'X', 'Y'),
        ('위에서 본 뷰', 0, 2, 'X', 'Z'),
        ('옆에서 본 뷰', 2, 1, 'Z', 'Y'),  # 가로=Z(깊이), 세로=Y(높이)
    ]
    xlims = [(get_lim(comp, xi), get_lim(comp, yi)) for _, xi, yi, _, _ in views]

    color_raw  = 'white' if same_color else 'steelblue'
    color_comp = 'white' if same_color else 'tomato'

    rows = [
        (raw,  color_raw,  f'압축 전  |  {len(raw):,}개'),
        (comp, color_comp, f'압축 후  |  {len(comp):,}개  (66% 제거)'),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor('black')

    for row, (pts, color, rlabel) in enumerate(rows):
        for col, (vtitle, xi, yi, xl, yl) in enumerate(views):
            ax = axes[row][col]
            ax.set_facecolor('black')
            ax.scatter(pts[:, xi], pts[:, yi], s=0.4, alpha=0.4, c=color, rasterized=True)
            ax.set_xlim(*xlims[col][0])
            ax.set_ylim(*xlims[col][1])
            if col == 0:   # 앞에서 본 뷰: XY 반전
                ax.invert_xaxis()
                ax.invert_yaxis()
            elif col == 2:  # 옆에서 본 뷰: Z축 180도 → Y 반전
                ax.invert_yaxis()
            ax.set_xlabel(xl, color='#aaa', fontsize=18)
            ax.set_ylabel(yl, color='#aaa', fontsize=18)
            ax.tick_params(colors='#666', labelsize=16)
            for spine in ax.spines.values():
                spine.set_edgecolor('#333')
            if row == 0:
                ax.set_title(vtitle, fontsize=20, color='white', pad=6)

        fig.text(0.01, 0.75 - row * 0.5, rlabel, va='center', ha='left',
                 fontsize=20, color=color, rotation=90)

    title = 'Gaussian 중심점 분포 비교 (단색)' if same_color else 'Gaussian 중심점 분포 비교'
    fig.suptitle(title, fontsize=26, color='white', y=1.01)
    plt.tight_layout(rect=[0.04, 0, 1, 1])
    return fig


if __name__ == '__main__':
    raw  = load_xyz(RAW_PATH)
    comp = load_xyz(COMP_PATH)
    print(f'압축 전: {len(raw):,}개  /  압축 후: {len(comp):,}개')

    fig1 = make_plot(raw, comp, same_color=False)
    fig1.savefig(OUT_COLOR, dpi=150, bbox_inches='tight', facecolor='black')
    print(f'저장: {OUT_COLOR}')

    fig2 = make_plot(raw, comp, same_color=True)
    fig2.savefig(OUT_WHITE, dpi=150, bbox_inches='tight', facecolor='black')
    print(f'저장: {OUT_WHITE}')
