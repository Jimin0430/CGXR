# 스마트폰 영상 기반 3D Gaussian Splatting의 End-to-End 무선 파이프라인: 서버 사이드 Python 직렬화와 Unity 런타임 로더 설계

**An End-to-End Wireless Pipeline for 3D Gaussian Splatting from Smartphone Video: Server-Side Python Serialization and Unity Runtime Loader Design**

---

최지민O, 김종현*

O인하대학교 경제학과/소프트웨어융합공학과, *인하대학교 인공지능공학과/디자인테크놀로지학과

e-mail: tangbole@naver.com, jonghyunkim@inha.ac.kr

---

## 요 약

본 논문은 스마트폰으로 촬영한 영상으로부터 3D Gaussian Splatting(3DGS) 모델을 서버에서 학습·압축하고, 단일 이진 파일로 변환하여 무선 전송 후 모바일에서 실시간으로 렌더링하는 End-to-End 파이프라인을 제안한다. 핵심 기여는 두 가지다. 첫째, PLY를 Unity 모바일 렌더러 전용 이진 포맷(.unitygs)으로 서버에서 미리 변환하는 **Python 기반 서버 사이드 직렬화**를 설계하였다. Unity Editor batch-mode 방식을 포기하고 순수 Python으로 구현함으로써 서버에 Unity 설치 없이 배포 가능하며, 쿼터니언 순서 변환·컬러 수식·SH 채널 재배열·Morton 3D 재정렬을 포함한 포맷 정확성을 모두 해결하였다. 둘째, Unity ScriptableObject API의 메인 스레드 전용 제약과 GaussianSplatRenderer의 OnEnable 타이밍 문제를 해결하는 **스레드 분리형 런타임 로더**를 설계하였다. iPhone 13 기준 45 FPS, 1.8초 에셋 로딩을 달성하였으며, ~5.5 MB 파일에 degree-2 SH 색상 정보가 완전히 보존된다.

▸ **Keyword**: 3D Gaussian Splatting, 모바일 실시간 렌더링, 서버 사이드 직렬화, End-to-End 파이프라인, Unity 런타임 로더

---

## I. Introduction

스마트폰으로 촬영한 영상으로부터 3D 장면을 복원하고 동일한 스마트폰에서 실시간으로 렌더링하는 End-to-End 파이프라인을 실현하려면 세 가지 구조적 한계를 극복해야 한다.

첫째, 3DGS[1] 학습은 수십 GB VRAM을 전제로 설계되어 있어 모바일에서 직접 수행할 수 없다. 둘째, 압축 전 PLY 파일은 수십 MB 이상으로 무선 전송에 부담이 된다. 셋째, 연구용 PLY 포맷과 Unity 모바일 렌더러가 요구하는 이진 에셋 형식 사이의 호환성 격차가 존재한다. PLY를 모바일에서 런타임에 변환하면 GPU 버퍼 재구성, 쿼터니언 재정렬, SH 채널 재배열 등의 비용이 초기 렌더링 지연으로 직결된다.

본 연구는 이 세 문제를 서버-클라이언트 분산 구조로 해결한다. 학습·압축·포맷 변환을 서버에서 처리하고, 모바일은 단일 이진 파일을 수신하는 즉시 렌더링을 시작한다. 특히 기존 Unity GaussianSplatting 패키지[6]가 제공하는 에디터 기반 변환을 서버에서 재현하기 위해 **Python 기반 순수 구현**으로 전환한 설계 결정과, Unity 런타임 API의 비공개 제약을 해결한 **스레드 분리 로더**가 이 연구의 핵심 기여다.

---

## II. Preliminaries

### 1. Related Works

#### 1.1 3D Gaussian Splatting

3DGS[1]는 장면을 수많은 3차원 Gaussian의 집합으로 표현한다. 각 Gaussian은 위치 μ ∈ ℝ³, 공분산 행렬 Σ = RSS^T R^T, 불투명도 α, 그리고 구면 조화 함수(SH) 계수로 인코딩된 색상 c를 파라미터로 가진다. 렌더링은 각 Gaussian을 카메라 시점으로 투영한 뒤 깊이 순 정렬 후 α-compositing을 적용한다.

#### 1.2 LightGaussian

LightGaussian[2]은 3DGS PLY를 경량화하기 위한 3단계 압축 기법이다. (1) 중요도 Score(G_i) = α_i · σ_i 기반 Pruning, (2) SH Degree 3(rest 45개)→2(rest 24개) 지식 증류, (3) VecTree 벡터 양자화(Codebook 크기 8,192)를 순차 적용한다. 본 연구에서는 이 출력 PLY를 Unity 모바일 렌더러 호환 포맷으로 변환하는 과정의 구체적 구현 문제를 해결한다.

#### 1.3 SAM2

SAM2[4]는 첫 프레임에서 생성한 마스크를 영상 전체로 자동 전파하는 범용 분할 모델이다. 본 파이프라인에서는 배경을 사전 제거하여 불필요한 배경 Gaussian 생성을 방지하고 전경 품질을 향상시킨다.

#### 1.4 Unity GaussianSplatting

aras-p의 Unity GaussianSplatting 패키지[6]는 GaussianSplatRenderer와 GaussianSplatAsset을 제공한다. 에디터에서 PLY를 임포트할 때 내부적으로 position, other(회전+스케일), color(Morton-swizzled 텍스처), sh(SHTableItemFloat32), chunk(경계 정보) 등 5개 TextAsset으로 분할 저장한다. 런타임에서 GaussianSplatAsset을 동적으로 생성하는 공개 API는 존재하지 않아, 본 연구에서 리플렉션 기반 런타임 조립 방법을 독립적으로 개발하였다.

---

## III. The Proposed Scheme

### 1. System Architecture

전체 시스템은 모바일 클라이언트, 학습 서버, 무선 전송 계층으로 구성된다(Fig. 1 참조). 서버는 FastAPI 기반 REST API를 제공하며, 학습 파이프라인은 BackgroundTasks를 통해 비동기 실행된다. 파이프라인 각 단계(extracting → sam2 → training → pruning → distilling → quantizing → converting → done)는 job JSON에 기록되며, 모바일 클라이언트는 2초 간격으로 `/status`를 폴링하여 진행률을 표시한다. 수 시간의 학습 중에도 모바일의 상태 폴링이 차단 없이 처리되는 것이 BackgroundTasks 구조의 이점이다.

### 2. Server Pipeline

#### 2.1 영상 전처리 및 3DGS 학습

업로드된 영상에서 10 FPS로 프레임을 추출하고 pycolmap[5]으로 SfM 카메라 포즈를 추정한다. SAM2를 적용하여 첫 프레임의 배경 마스크를 전체 프레임에 전파한 뒤, 배경이 제거된 프레임으로 3DGS를 학습한다(30,000 iter 초기 학습 + 35,000 iter 미세 조정). 이후 LightGaussian 3단계 압축을 적용한다: Pruning(66% 제거) → SH 증류(degree 3→2, 40,000 iter) → VecTree 양자화(비율 0.6, Codebook 8,192).

#### 2.2 Python 기반 서버 사이드 직렬화 (핵심 기여 1)

PLY를 모바일 렌더러 호환 포맷으로 변환하는 방식으로 최초에는 서버에서 Unity Editor를 batch-mode로 실행하는 방안을 구현하였다. 그러나 이 접근은 서버에 Unity 라이선스와 프로젝트 설치가 요구되고, headless 실행 환경이 불안정하여 배포가 어렵다는 문제가 있었다. 이를 해결하기 위해 Unity GaussianSplatting 패키지의 내부 변환 로직을 역분석하여 **순수 Python으로 재구현**하였다.

변환 결과물인 `.unitygs` 파일의 구조는 다음과 같다:

```
Asset = [Header | PositionBuffer | ScaleBuffer | RotationBuffer | ColorBuffer | SHCoeffBuffer]
```

| 버퍼 | 크기 (N=22,935) | 내용 및 변환 | 누적 크기 |
|------|---------------|-------------|---------|
| Header | 13 B | Magic(4B) + Version(4B) + Count(4B) + hasSH(1B) | 13 B |
| PositionBuffer | N×12 B | xyz float32, 선형 좌표 | ~280 KB |
| ScaleBuffer | N×12 B | exp() 적용 (PLY log-scale → linear) | ~547 KB |
| RotationBuffer | N×16 B | xyzw float32, 정규화 (PLY wxyz → xyzw 재순서) | ~903 KB |
| ColorBuffer | N×16 B | f_dc × SH_C0 + 0.5, sigmoid(opacity) | ~1.26 MB |
| SHCoeffBuffer | N×192 B | 48 floats, 채널 재배열 + zero-padding | ~5.5 MB |

모든 버퍼는 float32로 GPU가 직접 읽을 수 있는 stride와 alignment를 서버 단계에서 맞춰 두므로, 모바일은 수신 즉시 GPU 버퍼에 직접 매핑하여 렌더링을 시작할 수 있다.

PLY→.unitygs 변환에서 포맷 정확성을 확보하기 위해 해결해야 했던 주요 문제는 다음과 같다.

**쿼터니언 축 순서.** 3DGS PLY는 (w, x, y, z) 순서로 저장하지만 Unity 로더는 (x, y, z, w) 순서를 기대한다. 이를 혼동하면 모든 Gaussian의 방향이 잘못 해석되어 장면 전체가 깨진다.

**컬러 활성화 수식.** 초기 구현에서는 opacity와 같이 DC 색상에도 sigmoid를 적용하였다. 그러나 Unity HLSL의 ShadeSH는 `color = f_dc × SH_C0 + 0.5`의 선형 변환을 전제하므로, sigmoid를 적용하면 색상이 과포화된다.

**Morton 3D 재정렬.** Unity GaussianSplatting 에디터는 Splat을 3D Morton 코드 순서로 재정렬한 뒤 저장한다. 이 재정렬 없이 렌더링하면 깊이 정렬 근사의 품질이 저하되어 블렌딩 아티팩트가 증가한다. 에디터의 ReorderMorton 구현을 Python으로 포팅하였다.

**SH 채널 재배열.** PLY는 SH rest 계수를 채널별 순차 배열로 저장한다(R 채널 전체 → G → B). 반면 Unity의 SHTableItemFloat32는 계수별 인터리브 배열([R₀G₀B₀][R₁G₁B₁]...)을 요구한다. 이 두 형식을 혼동하면 RGB 채널이 서로 엇갈려 색상이 완전히 깨진다. 또한 LightGaussian의 degree 3→2 축소로 인해 24개 rest 계수를 48 float 슬롯(15 float3 + padding)에 zero-padding하여 배치해야 한다.

```python
rest_names = sorted([k for k in ply.dtype.names if k.startswith('f_rest_')],
                    key=lambda s: int(s.split('_')[-1]))
coeffs_per_ch = len(rest_names) // 3   # degree 무관: 3→8→15
sh = np.zeros((N, 48), dtype=np.float32)
for i in range(min(coeffs_per_ch, 15)):
    sh[:, i*3+0] = ply[rest_names[i]]                       # Rᵢ
    sh[:, i*3+1] = ply[rest_names[i + coeffs_per_ch]]       # Gᵢ
    sh[:, i*3+2] = ply[rest_names[i + 2*coeffs_per_ch]]     # Bᵢ
```

coeffs_per_ch를 동적으로 계산함으로써 degree 1·2·3 모두에서 올바르게 동작한다.

#### 2.3 무선 전송

변환 완료 후 서버는 단일 `.unitygs` 파일을 HTTP 엔드포인트로 제공한다. 모바일 클라이언트는 done 상태 확인 시 자동으로 다운로드를 시작한다. PLY 원본은 전송하지 않으며, 5개 파일 분리 전송 방식과 달리 단일 파일이므로 전송 예외 처리가 단순하다.

### 3. Mobile Rendering

#### 3.1 Unity 런타임 로더 스레드 분리 (핵심 기여 2)

`.unitygs` 파일을 수신하여 GaussianSplatRenderer를 런타임에 생성하는 과정에서 두 가지 비공개 API 제약이 있었다.

**제약 1 — ScriptableObject 메인 스레드 전용.** ScriptableObject.CreateInstance()와 TextAsset(byte[]) 생성자는 Unity 메인 스레드에서만 호출 가능하다. 이를 백그라운드 스레드에서 호출하면 Unity 내부 상태 손상으로 크래시가 발생한다. 반면 ~5.5 MB 파일의 I/O 블로킹을 메인 스레드에서 수행하면 렌더링 프레임이 멈춘다. 이를 해결하기 위해 `Task.Run()`으로 백그라운드에서 파일을 파싱하여 순수 float[] 배열(RawSplatData)만 채우고, 메인 스레드에서 `yield return null`로 완료를 기다린 뒤 Unity API를 호출하는 방식으로 역할을 분리하였다.

**제약 2 — GaussianSplatRenderer OnEnable 타이밍.** AddComponent<GaussianSplatRenderer>()를 호출하면 Unity는 즉시 OnEnable()을 실행한다. 이 시점에 m_Asset이 null이면 렌더러가 빈 상태로 초기화되며, 이후 m_Asset을 설정해도 효과가 없다.

```csharp
splatObj.SetActive(false);                            // OnEnable 억제
var r = splatObj.AddComponent<GaussianSplatRenderer>();
SetField(r, "m_Asset", asset);                        // m_Asset 선 설정
splatObj.SetActive(true);                             // 여기서 OnEnable 실행
```

SetActive(false)로 OnEnable 실행을 억제하고, m_Asset 설정 후 SetActive(true)를 호출하여 OnEnable이 정상적으로 asset을 참조하도록 하였다.

#### 3.2 GPU 스레드 그룹 크기 제한

모바일 GPU는 동시 처리 스레드 수가 제한적이다. 기본 설정 그대로 실행하면 스레드 오버헤드로 렌더링 실패 또는 심각한 프레임 드롭이 발생한다. iPhone 13(A15 Bionic) 기준으로 Compute Shader 스레드 그룹 크기를 64로 제한하였을 때 안정적인 렌더링이 가능하였다.

#### 3.3 정렬(Sorting) 임시 생략

3DGS 렌더링의 정확한 α-compositing을 위해서는 카메라 깊이 기준 매 프레임 Gaussian 정렬이 필요하다. 그러나 GPU 기반 정렬은 모바일에서 프레임당 수십 ms 오버헤드를 유발한다. 본 연구에서는 실시간 성능 확보를 위해 정렬을 임시로 생략하였으며, 이로 인해 반투명 영역에서 블렌딩 순서 오류가 일부 발생한다. 향후 Mobile-GS[3] 기법 접목으로 해결할 계획이다.

---

## IV. Design Parameters and Assumptions

### 1. 주요 파라미터

| 항목 | 값 |
|------|---|
| 프레임 추출 속도 | 10 FPS |
| 3DGS 초기 학습 반복 | 30,000회 |
| 3DGS 미세 조정 반복 | 35,000회 |
| Pruning 비율 | 66% |
| Distillation 학습 반복 | 40,000회 |
| Distillation 이후 SH Degree | 2 (rest 계수 24개) |
| VecTree VQ 비율 / Codebook 크기 | 0.6 / 8,192 |
| 상태 조회 주기 | 2초 |
| 모바일 GPU 스레드 그룹 크기 | 64 (iPhone 13 기준) |
| 이진 파일 정밀도 | float32 (GPU 직접 매핑) |

### 2. 가정 조건

- 영상은 하나의 주요 전경 객체를 중심으로 촬영한다.
- 학습 서버에는 CUDA를 지원하는 GPU가 탑재되어 있다.
- 모바일 기기는 안정적인 Wi-Fi 또는 5G 연결을 유지한다.

---

## V. Results

실제 스마트폰으로 촬영한 영상(MOV, 129프레임 추출)을 사용하여 파이프라인을 수행하였다. 서버는 NVIDIA RTX 계열 GPU 환경, 모바일 기기는 iPhone 13(A15 Bionic, RAM 6 GB)이다.

### 1. 파이프라인 단계별 결과

| 단계 | Splat 수 | 파일 크기 | 비고 |
|------|---------|---------|-----|
| 3DGS 30K iter | 67,455 | 16 MB | 초기 학습 |
| Pruning 66% | 22,935 | 5.5 MB | 66.0% 제거 |
| SH 증류 degree 2 | 22,935 | 3.6 MB | rest 45→24개 |
| VecTree 양자화 | 22,935 | 3.76 MB | npz 내부 1.2 MB |
| **.unitygs 변환** | **22,935** | **~5.5 MB** | **SH float32 포함** |

PLY 기준 압축률은 16 MB → 3.6 MB = **4.4배**이다. .unitygs는 GPU 직접 매핑을 위해 float32를 유지하므로 VecTree PLY보다 크다. SH를 생략할 경우(hasSH=false) ~1.3 MB로 감소하지만 시점 의존 색상 변화가 소실된다.

### 2. 모바일 렌더링 성능

| 지표 | 값 |
|------|---|
| 평균 FPS | **45 FPS** |
| 프레임 시간 | 22 ms |
| 에셋 로딩 시간 | **1.8초** |
| 전송 파일 크기 (SH 포함) | **~5.5 MB** |
| 런타임 메모리 | 520 MB |
| GPU 스레드 그룹 크기 | 64 |

에셋 수신 완료 후 렌더링 시작까지 1.8초가 소요되었다. 정렬(depth sorting)은 현재 비활성화 상태이며, 일부 반투명 스플랫의 블렌딩 순서가 부정확할 수 있다.

---

## VI. Conclusions

본 논문은 스마트폰 영상 기반 3DGS의 End-to-End 무선 렌더링 파이프라인을 제안하고, 실제 구현에서 마주친 두 가지 핵심 기술 문제를 해결하였다.

첫째, PLY 변환을 Unity Editor batch-mode가 아닌 **순수 Python으로 구현**함으로써 서버 배포 요건을 단순화하고 단일 .unitygs 파일로 무선 전송 구조를 실현하였다. 이 과정에서 쿼터니언 순서, 컬러 수식, Morton 재정렬, SH 채널 재배열 등 포맷 정확성 문제를 모두 해결하였다.

둘째, Unity ScriptableObject의 메인 스레드 전용 제약과 GaussianSplatRenderer의 OnEnable 타이밍 문제를 **스레드 분리 Coroutine + SetActive(false) 선행 비활성화** 기법으로 해결하여 안정적인 런타임 에셋 로딩을 구현하였다.

iPhone 13에서 45 FPS, 1.8초 로딩의 실시간 렌더링을 달성하였으며, ~5.5 MB 파일에 degree-2 SH 색상 정보가 완전히 보존된다. 향후에는 GPU 기반 실시간 정렬 도입, float16 정밀도 적용을 통한 전송 크기 추가 절감, ARKit/ARCore 연동을 통한 증강 현실 환경 확장을 목표로 한다.

---

## References

[1] B. Kerbl et al., "3D Gaussian Splatting for Real-Time Radiance Field Rendering," ACM TOG, vol. 42, no. 4, 2023.

[2] Z. Fan et al., "LightGaussian: Unbounded 3D Gaussian Compression with 15x Reduction and 200+ FPS," arXiv:2311.17245, 2023.

[3] X. Du et al., "Mobile-GS: Real-time Gaussian Splatting for Mobile Devices," arXiv:2603.11531, 2026.

[4] N. Ravi et al., "SAM 2: Segment Anything in Images and Videos," arXiv:2408.00714, 2024.

[5] J. L. Schönberger, J.-M. Frahm, "Structure-from-Motion Revisited," CVPR, pp. 4104–4113, 2016.

[6] A. Pranckevičius, "UnityGaussianSplatting," GitHub, 2024. https://github.com/aras-p/UnityGaussianSplatting.

[7] B. Mildenhall et al., "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis," ECCV, pp. 405–421, 2020.
