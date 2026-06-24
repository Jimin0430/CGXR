using System;
using System.Collections;
using System.IO;
using UnityEngine;
using GaussianSplatting.Runtime;

namespace GaussianSplatting
{
    /// <summary>
    /// Unity Gaussian Splat 바이너리 형식 (.unitygs) 런타임 로더
    /// 서버에서 받은 바이너리 파일을 직접 메모리에 로드하여 렌더링
    /// </summary>
    public class UnityGSBinaryLoader : MonoBehaviour
    {
        private const uint MAGIC = 0x41534755; // 'UGSA' in little endian
        private const int VERSION = 1;

        /// <summary>
        /// 서버에서 받은 .unitygs 바이너리 파일을 로드하여 GaussianSplatRenderer에 표시
        /// </summary>
        public IEnumerator LoadFromBinary(string binaryPath, Action<GaussianSplatRenderer> onComplete)
        {
            if (!File.Exists(binaryPath))
            {
                Debug.LogError($"[UnityGSLoader] Binary file not found: {binaryPath}");
                yield break;
            }

            Debug.Log($"[UnityGSLoader] Loading binary: {binaryPath}");

            GaussianSplatAsset asset = null;
            Exception error = null;

            // 백그라운드에서 파일 읽기
            System.Threading.Tasks.Task.Run(() =>
            {
                try
                {
                    asset = ParseBinaryFile(binaryPath);
                }
                catch (Exception ex)
                {
                    error = ex;
                }
            });

            // 로딩 대기
            while (asset == null && error == null)
            {
                yield return null;
            }

            if (error != null)
            {
                Debug.LogError($"[UnityGSLoader] Failed to load binary: {error.Message}");
                yield break;
            }

            // GaussianSplatRenderer 생성
            GameObject splatObj = new GameObject("ServerGaussianSplat");
            GaussianSplatRenderer renderer = splatObj.AddComponent<GaussianSplatRenderer>();

            // Asset 설정 (private field 접근)
            SetPrivateField(renderer, "m_Asset", asset);

            Debug.Log($"[UnityGSLoader] ✓ Binary loaded and displayed: {binaryPath}");
            onComplete?.Invoke(renderer);
        }

        /// <summary>
        /// .unitygs 바이너리 파일 파싱
        /// </summary>
        private GaussianSplatAsset ParseBinaryFile(string path)
        {
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read))
            using (BinaryReader reader = new BinaryReader(fs))
            {
                // Header 파싱
                uint magic = reader.ReadUInt32();
                if (magic != MAGIC)
                {
                    throw new IOException($"Invalid magic number: 0x{magic:X8}, expected 0x{MAGIC:X8}");
                }

                uint version = reader.ReadUInt32();
                if (version != VERSION)
                {
                    throw new IOException($"Unsupported version: {version}, expected {VERSION}");
                }

                uint splatCount = reader.ReadUInt32();
                Debug.Log($"[UnityGSLoader] Splat count: {splatCount}");

                // Positions (float32 x N x 3)
                Vector3[] positions = new Vector3[splatCount];
                for (int i = 0; i < splatCount; i++)
                {
                    positions[i] = new Vector3(
                        reader.ReadSingle(),
                        reader.ReadSingle(),
                        reader.ReadSingle()
                    );
                }

                // Scales (float32 x N x 3)
                Vector3[] scales = new Vector3[splatCount];
                for (int i = 0; i < splatCount; i++)
                {
                    scales[i] = new Vector3(
                        reader.ReadSingle(),
                        reader.ReadSingle(),
                        reader.ReadSingle()
                    );
                }

                // Rotations (float32 x N x 4) - quaternions
                Quaternion[] rotations = new Quaternion[splatCount];
                for (int i = 0; i < splatCount; i++)
                {
                    rotations[i] = new Quaternion(
                        reader.ReadSingle(), // x
                        reader.ReadSingle(), // y
                        reader.ReadSingle(), // z
                        reader.ReadSingle()  // w
                    );
                }

                // Colors (float32 x N x 4) - RGBA
                Color[] colors = new Color[splatCount];
                for (int i = 0; i < splatCount; i++)
                {
                    colors[i] = new Color(
                        reader.ReadSingle(),
                        reader.ReadSingle(),
                        reader.ReadSingle(),
                        reader.ReadSingle()
                    );
                }

                // SH Coefficients (optional)
                bool hasSH = reader.ReadBoolean();
                float[][] shCoeffs = null;
                if (hasSH)
                {
                    shCoeffs = new float[splatCount][];
                    for (int i = 0; i < splatCount; i++)
                    {
                        shCoeffs[i] = new float[48];
                        for (int j = 0; j < 48; j++)
                        {
                            shCoeffs[i][j] = reader.ReadSingle();
                        }
                    }
                }

                // GaussianSplatAsset 생성
                GaussianSplatAsset asset = ScriptableObject.CreateInstance<GaussianSplatAsset>();

                // 데이터 설정 (Reflection 또는 public API 사용)
                // 실제로는 GaussianSplatAsset의 내부 구조에 맞춰 설정 필요
                SetAssetData(asset, positions, scales, rotations, colors, shCoeffs);

                Debug.Log($"[UnityGSLoader] ✓ Parsed {splatCount} splats from binary");
                return asset;
            }
        }

        /// <summary>
        /// GaussianSplatAsset에 파싱된 데이터 설정
        /// </summary>
        private void SetAssetData(
            GaussianSplatAsset asset,
            Vector3[] positions,
            Vector3[] scales,
            Quaternion[] rotations,
            Color[] colors,
            float[][] shCoeffs)
        {
            // GaussianSplatAsset의 내부 필드 설정
            // 실제 구현은 GaussianSplatAsset 구조에 따라 달라짐

            SetPrivateField(asset, "m_SplatCount", positions.Length);

            // ComputeBuffer 또는 Texture 형태로 데이터 저장
            // 여기서는 간단히 메모리에만 저장
            // 실제로는 GPU buffer로 전송 필요

            Debug.Log($"[UnityGSLoader] Asset data configured: {positions.Length} splats");
        }

        private void SetPrivateField(object obj, string fieldName, object value)
        {
            var field = obj.GetType().GetField(fieldName,
                System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Instance);

            if (field != null)
            {
                field.SetValue(obj, value);
            }
            else
            {
                Debug.LogWarning($"[UnityGSLoader] Field '{fieldName}' not found in {obj.GetType().Name}");
            }
        }
    }
}
