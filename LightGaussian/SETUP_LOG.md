# LightGaussian Setup Log

## 현재 상태 (2026-03-26)

### 완료된 것
- `LightGaussian/repo/` 클론 완료 (https://github.com/VITA-Group/LightGaussian)
- `.bat` 스크립트 4개 작성 완료
  - `0_setup.bat` — 환경 생성
  - `1_stage1_prune.bat` — Pruning + Finetune
  - `2_stage2_distill.bat` — SH Distillation
  - `3_stage3_quantize.bat` — VecTree Quantization
- 30,000 iter 가우시안 학습 완료
  - `output/point_cloud/iteration_30000/point_cloud.ply` (2,997,278개 가우시안, 709MB)
  - `output/chkpnt30000.pth` (LightGaussian Stage 1 입력용)

### 막힌 것
- `conda env create --file environment.yml` 에서 **Solving environment** 단계가 수 시간째 멈춰 있음
- conda가 패키지 버전 조합을 못 찾고 있는 상태

### 시도할 해결책
`mamba`를 사용해 더 빠르게 dependency 해결:
```bat
conda install -n base -c conda-forge mamba
mamba env create -f "D:\JM\cgxr\CGXR\LightGaussian\repo\environment.yml"
```

---

## environment.yml 내용

```yaml
name: lightgaussian
channels:
  - pytorch
  - conda-forge
  - defaults
dependencies:
  - cudatoolkit=11.6
  - plyfile=0.8.1
  - python=3.9
  - pip=22.3.1
  - pytorch=1.12.1
  - torchaudio=0.12.1
  - torchvision=0.13.1
  - setuptools=69.5.1
  - tqdm
  - icecream
  - pip:
    - submodules/compress-diff-gaussian-rasterization
    - submodules/simple-knn
```

---

## 전체 파이프라인 목표

```
output/chkpnt30000.pth  (30k iter 학습 결과)
        ↓ Stage 1: Pruning + Finetune (35,000 iter)
output_lightgaussian/stage1_pruned/chkpnt35000.pth
        ↓ Stage 2: SH Distillation (40,000 iter)
output_lightgaussian/stage2_distilled/point_cloud/iteration_40000/point_cloud.ply
        ↓ Stage 3: VecTree Quantization
output_lightgaussian/stage3_quantized/  (최종 압축 모델, ~15x 압축)
```

## 입력 데이터 경로
- Source (이미지 + COLMAP): `D:\JM\cgxr\CGXR\Extract_SfM`
- 30k 체크포인트: `D:\JM\cgxr\CGXR\output\chkpnt30000.pth`
