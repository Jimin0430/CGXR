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


SIDE_ROT_DEG = 15  # 옆에서 본 뷰 Y축 기준 오른쪽 회전각 (도)

def _side_project(pts):
    """Y축 기준 SIDE_ROT_DEG만큼 오른쪽 회전 후 ZY 평면 투영."""
    t = np.radians(SIDE_ROT_DEG)
    c, s = np.cos(t), np.sin(t)
    z_rot = -pts[:, 0] * s + pts[:, 2] * c  # new Z (horizontal)
    return z_rot, pts[:, 1]                  # (Z_rot, Y)


def make_plot(raw, comp, same_color=False):
    views = [
        ('앞에서 본 뷰', 0, 1, 'X', 'Y'),
        ('위에서 본 뷰', 0, 2, 'X', 'Z'),
        ('옆에서 본 뷰', None, None, 'Z', 'Y'),  # 회전 투영 사용
    ]

    # 축 범위: 앞/위는 comp 퍼센타일, 옆은 회전 후 comp 기준
    comp_side_z, comp_side_y = _side_project(comp)
    xlims = [
        (get_lim(comp, 0), get_lim(comp, 1)),
        (get_lim(comp, 0), get_lim(comp, 2)),
        ((np.percentile(comp_side_z, 1) - 0.3, np.percentile(comp_side_z, 99) + 0.3),
         (np.percentile(comp_side_y, 1) - 0.3, np.percentile(comp_side_y, 99) + 0.3)),
    ]

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

            if col == 2:
                px, py = _side_project(pts)
            else:
                px, py = pts[:, xi], pts[:, yi]

            ax.scatter(px, py, s=0.4, alpha=0.4, c=color, rasterized=True)
            ax.set_xlim(*xlims[col][0])
            ax.set_ylim(*xlims[col][1])
            if col == 0:   # 앞에서 본 뷰: XY 반전
                ax.invert_xaxis()
                ax.invert_yaxis()
            elif col == 2:  # 옆에서 본 뷰: Y 반전
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
