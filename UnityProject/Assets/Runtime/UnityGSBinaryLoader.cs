using System;
using System.Collections;
using System.IO;
using UnityEngine;
using GaussianSplatting.Runtime;

namespace GaussianSplatting
{
    /// <summary>
    /// Unity Gaussian Splat 바이너리 형식 (.unitygs) 런타임 로더.
    /// 서버에서 받은 바이너리 파일을 직접 메모리에 로드하여 GaussianSplatRenderer에 전달.
    /// </summary>
    public class UnityGSBinaryLoader : MonoBehaviour
    {
        private const uint MAGIC   = 0x41534755; // 'UGSA'
        private const int  VERSION = 1;
        private const int  TEX_W   = 2048;       // GaussianSplatAsset.kTextureWidth

        // ── 공개 진입점 ──────────────────────────────────────────────────────────

        public IEnumerator LoadFromBinary(string binaryPath, Action<GaussianSplatRenderer> onComplete)
        {
            if (!File.Exists(binaryPath))
            {
                Debug.LogError($"[UnityGSLoader] File not found: {binaryPath}");
                onComplete?.Invoke(null);
                yield break;
            }

            Debug.Log($"[UnityGSLoader] Loading: {binaryPath}");

            GaussianSplatAsset asset = null;
            Exception loadError     = null;

            var task = System.Threading.Tasks.Task.Run(() =>
            {
                try   { asset = ParseBinaryFile(binaryPath); }
                catch (Exception ex) { loadError = ex; }
            });

            while (!task.IsCompleted)
                yield return null;

            if (loadError != null)
            {
                Debug.LogError($"[UnityGSLoader] Parse failed: {loadError.Message}\n{loadError.StackTrace}");
                onComplete?.Invoke(null);
                yield break;
            }

            // GaussianSplatRenderer 생성 (메인 스레드)
            GameObject splatObj = new GameObject("ServerGaussianSplat");
            GaussianSplatRenderer renderer = splatObj.AddComponent<GaussianSplatRenderer>();
            SetPrivateField(renderer, "m_Asset", asset);

            Debug.Log($"[UnityGSLoader] Loaded {asset.splatCount:N0} splats");
            onComplete?.Invoke(renderer);
        }

        // ── 파일 파싱 (백그라운드 스레드) ────────────────────────────────────────

        private GaussianSplatAsset ParseBinaryFile(string path)
        {
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read))
            using (var reader = new BinaryReader(fs))
            {
                uint magic = reader.ReadUInt32();
                if (magic != MAGIC)
                    throw new IOException($"Invalid magic: 0x{magic:X8}");

                uint version = reader.ReadUInt32();
                if (version != VERSION)
                    throw new IOException($"Unsupported version: {version}");

                int n = (int)reader.ReadUInt32();
                Debug.Log($"[UnityGSLoader] splatCount={n}");

                // Positions (float32 × N × 3)
                var positions = new Vector3[n];
                for (int i = 0; i < n; i++)
                    positions[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());

                // Scales (float32 × N × 3)
                var scales = new Vector3[n];
                for (int i = 0; i < n; i++)
                    scales[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());

                // Rotations (float32 × N × 4, xyzw)
                var rotations = new Quaternion[n];
                for (int i = 0; i < n; i++)
                    rotations[i] = new Quaternion(reader.ReadSingle(), reader.ReadSingle(),
                                                  reader.ReadSingle(), reader.ReadSingle());

                // Colors (float32 × N × 4, RGBA)
                var colors = new Color[n];
                for (int i = 0; i < n; i++)
                    colors[i] = new Color(reader.ReadSingle(), reader.ReadSingle(),
                                          reader.ReadSingle(), reader.ReadSingle());

                // SH coefficients (optional, float32 × N × 48)
                bool hasSH = reader.ReadBoolean();
                float[] shFlat = null;
                if (hasSH)
                {
                    shFlat = new float[n * 48];
                    for (int i = 0; i < shFlat.Length; i++)
                        shFlat[i] = reader.ReadSingle();
                }

                return BuildAsset(n, positions, scales, rotations, colors, hasSH, shFlat);
            }
        }

        // ── GaussianSplatAsset 조립 ───────────────────────────────────────────

        private static GaussianSplatAsset BuildAsset(
            int n,
            Vector3[]   positions,
            Vector3[]   scales,
            Quaternion[] rotations,
            Color[]     colors,
            bool        hasSH,
            float[]     shFlat)
        {
            // 전체 bounds
            var bMin = new Vector3(float.MaxValue,  float.MaxValue,  float.MaxValue);
            var bMax = new Vector3(float.MinValue, float.MinValue, float.MinValue);
            for (int i = 0; i < n; i++)
            {
                bMin = Vector3.Min(bMin, positions[i]);
                bMax = Vector3.Max(bMax, positions[i]);
            }

            // === 포지션 데이터 (VectorFormat.Float32 = 12 bytes/splat) ===
            byte[] posBytes = new byte[n * 12];
            for (int i = 0; i < n; i++)
            {
                int off = i * 12;
                WriteFloat(posBytes, off,     positions[i].x);
                WriteFloat(posBytes, off + 4, positions[i].y);
                WriteFloat(posBytes, off + 8, positions[i].z);
            }

            // === Other 데이터 (packed rotation 4B + scale Float32 12B = 16 bytes/splat) ===
            byte[] otherBytes = new byte[n * 16];
            for (int i = 0; i < n; i++)
            {
                int off = i * 16;
                WriteUInt(otherBytes, off,      PackRotation(rotations[i]));
                WriteFloat(otherBytes, off + 4,  scales[i].x);
                WriteFloat(otherBytes, off + 8,  scales[i].y);
                WriteFloat(otherBytes, off + 12, scales[i].z);
            }

            // === 컬러 데이터 (ColorFormat.Float32x4, Morton-swizzled texture) ===
            int texH       = CalcTexHeight(n);
            int totalPixels = TEX_W * texH;
            byte[] colorBytes = new byte[totalPixels * 16]; // 4 floats × 4 bytes
            for (int i = 0; i < n; i++)
            {
                int mIdx = MortonIndex(i);
                int off  = mIdx * 16;
                WriteFloat(colorBytes, off,      colors[i].r);
                WriteFloat(colorBytes, off + 4,  colors[i].g);
                WriteFloat(colorBytes, off + 8,  colors[i].b);
                WriteFloat(colorBytes, off + 12, colors[i].a);
            }

            // === SH 데이터 (SHFormat.Float32 = SHTableItemFloat32, 192 bytes/splat) ===
            // SHTableItemFloat32: sh1..sh15 (float3 each) + shPadding (float3) = 48 floats = 192 bytes
            byte[] shBytes;
            var shFmt = GaussianSplatAsset.SHFormat.Float32;
            if (hasSH && shFlat != null)
            {
                shBytes = new byte[n * 192];
                Buffer.BlockCopy(shFlat, 0, shBytes, 0, shBytes.Length);
            }
            else
            {
                // 빈 SH: band0만 있으면 SHFormat.Norm6 + 최소 데이터
                shBytes = new byte[0];
                shFmt   = GaussianSplatAsset.SHFormat.Norm6;
            }

            // === 청크 데이터 (per-256-splat bounds) ===
            byte[] chunkBytes = BuildChunkData(n, positions, colors);

            // === GaussianSplatAsset 생성 ===
            var asset = ScriptableObject.CreateInstance<GaussianSplatAsset>();
            asset.Initialize(
                n,
                GaussianSplatAsset.VectorFormat.Float32,   // pos
                GaussianSplatAsset.VectorFormat.Float32,   // scale
                GaussianSplatAsset.ColorFormat.Float32x4,  // color
                shFmt,
                bMin, bMax,
                cameras: null);

            var chunkTA = new TextAsset(chunkBytes);
            var posTA   = new TextAsset(posBytes);
            var otherTA = new TextAsset(otherBytes);
            var colorTA = new TextAsset(colorBytes);
            var shTA    = new TextAsset(shBytes);

            asset.SetAssetFiles(chunkTA, posTA, otherTA, colorTA, shTA);
            return asset;
        }

        // ── 헬퍼: 청크 데이터 빌드 ───────────────────────────────────────────────

        private static byte[] BuildChunkData(int n, Vector3[] positions, Color[] colors)
        {
            // ChunkInfo layout (64 bytes):
            //   uint colR, colG, colB, colA  (16 bytes)
            //   float2 posX, posY, posZ       (24 bytes)
            //   uint sclX, sclY, sclZ         (12 bytes)
            //   uint shR, shG, shB            (12 bytes)
            int chunkCount = (n + 255) / 256;
            byte[] data    = new byte[chunkCount * 64];

            for (int c = 0; c < chunkCount; c++)
            {
                int start = c * 256;
                int end   = Math.Min(start + 256, n);

                // position min/max
                var pMin = new Vector3(float.MaxValue,  float.MaxValue,  float.MaxValue);
                var pMax = new Vector3(float.MinValue, float.MinValue, float.MinValue);
                for (int i = start; i < end; i++)
                {
                    pMin = Vector3.Min(pMin, positions[i]);
                    pMax = Vector3.Max(pMax, positions[i]);
                }

                int off = c * 64;
                // colR/G/B/A (uint, offset 0-15) — zero for Float32 format
                // posX float2 at offset 16
                WriteFloat(data, off + 16, pMin.x);
                WriteFloat(data, off + 20, pMax.x);
                // posY at offset 24
                WriteFloat(data, off + 24, pMin.y);
                WriteFloat(data, off + 28, pMax.y);
                // posZ at offset 32
                WriteFloat(data, off + 32, pMin.z);
                WriteFloat(data, off + 36, pMax.z);
                // sclX/Y/Z (uint, offset 40-51) — zero for Float32 scale
                // shR/G/B  (uint, offset 52-63) — zero
            }
            return data;
        }

        // ── 헬퍼: 회전 패킹 (Smallest-Three, 10-10-10-2 bits) ──────────────────

        private static uint PackRotation(Quaternion q)
        {
            // normalize
            float len = Mathf.Sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w);
            if (len > 1e-6f) { q.x /= len; q.y /= len; q.z /= len; q.w /= len; }

            float[] comps = { q.x, q.y, q.z, q.w };

            // find largest-magnitude component
            int maxIdx = 0;
            float maxAbs = Mathf.Abs(comps[0]);
            for (int i = 1; i < 4; i++)
            {
                float a = Mathf.Abs(comps[i]);
                if (a > maxAbs) { maxAbs = a; maxIdx = i; }
            }

            // ensure positive sign for the largest component (so we can recover it)
            float sign = comps[maxIdx] >= 0f ? 1f : -1f;

            // encode the other three: range [-1/√2, +1/√2] → [0, 1023]
            const float range = 0.70710678118f; // 1/√2
            uint[] enc = new uint[3];
            int j = 0;
            for (int i = 0; i < 4; i++)
            {
                if (i == maxIdx) continue;
                float v = comps[i] * sign;
                enc[j++] = (uint)Mathf.Clamp(Mathf.RoundToInt((v / range + 1f) * 511.5f), 0, 1023);
            }

            return ((uint)maxIdx << 30) | (enc[0] << 20) | (enc[1] << 10) | enc[2];
        }

        // ── 헬퍼: Morton 스위즐 인덱스 ─────────────────────────────────────────

        private static int CalcTexHeight(int n)
        {
            int h = Math.Max(1, (n + TEX_W - 1) / TEX_W);
            h = (h + 15) / 16 * 16; // round up to tile height
            return h;
        }

        private static int MortonIndex(int splatIdx)
        {
            int x      = splatIdx % TEX_W;
            int y      = splatIdx / TEX_W;
            int tileX  = x / 16;
            int tileY  = y / 16;
            int localX = x % 16;
            int localY = y % 16;
            int tilesPerRow = TEX_W / 16;
            return (tileY * tilesPerRow + tileX) * 256 + Morton2D(localX, localY);
        }

        // 4-bit interleave (x at even bits, y at odd bits)
        private static int Morton2D(int x, int y)
        {
            x = (x | (x << 8)) & 0x00FF;
            x = (x | (x << 4)) & 0x0F0F;
            x = (x | (x << 2)) & 0x3333;
            x = (x | (x << 1)) & 0x5555;

            y = (y | (y << 8)) & 0x00FF;
            y = (y | (y << 4)) & 0x0F0F;
            y = (y | (y << 2)) & 0x3333;
            y = (y | (y << 1)) & 0x5555;

            return x | (y << 1);
        }

        // ── 헬퍼: 바이트 쓰기 (little-endian) ──────────────────────────────────

        private static void WriteFloat(byte[] buf, int off, float v)
        {
            byte[] b = BitConverter.GetBytes(v);
            buf[off]     = b[0];
            buf[off + 1] = b[1];
            buf[off + 2] = b[2];
            buf[off + 3] = b[3];
        }

        private static void WriteUInt(byte[] buf, int off, uint v)
        {
            buf[off]     = (byte)(v);
            buf[off + 1] = (byte)(v >> 8);
            buf[off + 2] = (byte)(v >> 16);
            buf[off + 3] = (byte)(v >> 24);
        }

        // ── 리플렉션 헬퍼 ─────────────────────────────────────────────────────

        private static void SetPrivateField(object obj, string fieldName, object value)
        {
            var field = obj.GetType().GetField(
                fieldName,
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            if (field != null)
                field.SetValue(obj, value);
            else
                Debug.LogWarning($"[UnityGSLoader] Field '{fieldName}' not found in {obj.GetType().Name}");
        }
    }
}
