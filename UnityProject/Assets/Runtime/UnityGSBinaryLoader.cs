using System;
using System.Collections;
using System.IO;
using UnityEngine;
using GaussianSplatting.Runtime;

namespace GaussianSplatting
{
    /// <summary>
    /// .unitygs 바이너리 파일 로더.
    /// 백그라운드 스레드에서 raw float 데이터만 읽고,
    /// GaussianSplatAsset 조립과 렌더러 생성은 모두 메인 스레드에서 수행.
    /// </summary>
    public class UnityGSBinaryLoader : MonoBehaviour
    {
        private const uint MAGIC   = 0x41534755;
        private const int  VERSION = 1;
        private const int  TEX_W   = 2048;

        // 백그라운드 스레드에서 채운 raw 데이터 컨테이너 (Unity API 없음)
        private class RawSplatData
        {
            public int        Count;
            public float[]    Positions;   // N*3
            public float[]    Scales;      // N*3
            public float[]    Rotations;   // N*4 xyzw
            public float[]    Colors;      // N*4 RGBA
            public bool       HasSH;
            public float[]    SHCoeffs;    // N*48 (null if !HasSH)
        }

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

            // ① 파일 I/O → 백그라운드 스레드 (Unity API 없음)
            RawSplatData raw  = null;
            Exception    err  = null;
            var task = System.Threading.Tasks.Task.Run(() =>
            {
                try   { raw = ReadRaw(binaryPath); }
                catch (Exception ex) { err = ex; }
            });
            while (!task.IsCompleted) yield return null;

            if (err != null)
            {
                Debug.LogError($"[UnityGSLoader] Read failed: {err.Message}\n{err.StackTrace}");
                onComplete?.Invoke(null);
                yield break;
            }

            // ② GaussianSplatAsset 조립 → 메인 스레드 (ScriptableObject, TextAsset)
            GaussianSplatAsset asset;
            try   { asset = BuildAsset(raw); }
            catch (Exception ex)
            {
                Debug.LogError($"[UnityGSLoader] BuildAsset failed: {ex.Message}\n{ex.StackTrace}");
                onComplete?.Invoke(null);
                yield break;
            }

            // ③ 렌더러 생성 → 비활성 상태로 먼저 만들고 asset 세팅 후 활성화
            //    AddComponent 직후 OnEnable이 즉시 실행되므로 SetActive(false) 선행 필수
            var splatObj = new GameObject("ServerGaussianSplat");
            splatObj.SetActive(false);

            var renderer = splatObj.AddComponent<GaussianSplatRenderer>();
            SetField(renderer, "m_Asset", asset);   // OnEnable 전에 세팅

            splatObj.SetActive(true);               // 여기서 OnEnable → 렌더러 초기화

            Debug.Log($"[UnityGSLoader] Rendered {asset.splatCount:N0} splats");
            onComplete?.Invoke(renderer);
        }

        // ── 1단계: 파일 파싱 (백그라운드 스레드, Unity API 사용 금지) ─────────────

        private static RawSplatData ReadRaw(string path)
        {
            using (var fs     = new FileStream(path, FileMode.Open, FileAccess.Read))
            using (var reader = new BinaryReader(fs))
            {
                uint magic = reader.ReadUInt32();
                if (magic != MAGIC)
                    throw new IOException($"Invalid magic: 0x{magic:X8}, expected 0x{MAGIC:X8}");

                uint ver = reader.ReadUInt32();
                if (ver != VERSION)
                    throw new IOException($"Unsupported version: {ver}");

                int n = (int)reader.ReadUInt32();

                var raw = new RawSplatData { Count = n };

                raw.Positions = ReadFloats(reader, n * 3);
                raw.Scales    = ReadFloats(reader, n * 3);
                raw.Rotations = ReadFloats(reader, n * 4);
                raw.Colors    = ReadFloats(reader, n * 4);

                raw.HasSH = reader.ReadBoolean();
                if (raw.HasSH)
                    raw.SHCoeffs = ReadFloats(reader, n * 48);

                return raw;
            }
        }

        private static float[] ReadFloats(BinaryReader r, int count)
        {
            var buf   = new float[count];
            var bytes = r.ReadBytes(count * 4);
            Buffer.BlockCopy(bytes, 0, buf, 0, bytes.Length);
            return buf;
        }

        // ── 2단계: GaussianSplatAsset 조립 (메인 스레드) ────────────────────────

        private static GaussianSplatAsset BuildAsset(RawSplatData raw)
        {
            int n = raw.Count;

            // 전체 bounds 계산
            var bMin = new Vector3(float.MaxValue,  float.MaxValue,  float.MaxValue);
            var bMax = new Vector3(float.MinValue, float.MinValue, float.MinValue);
            for (int i = 0; i < n; i++)
            {
                var p = new Vector3(raw.Positions[i*3], raw.Positions[i*3+1], raw.Positions[i*3+2]);
                bMin = Vector3.Min(bMin, p);
                bMax = Vector3.Max(bMax, p);
            }

            // === 포지션 데이터 (VectorFormat.Float32, 12 bytes/splat) ===
            byte[] posBytes = new byte[n * 12];
            Buffer.BlockCopy(raw.Positions, 0, posBytes, 0, posBytes.Length);

            // === Other 데이터 (packed rotation 4B + scale Float32 12B = 16 bytes/splat) ===
            byte[] otherBytes = new byte[n * 16];
            for (int i = 0; i < n; i++)
            {
                int off = i * 16;
                var q = new Quaternion(raw.Rotations[i*4], raw.Rotations[i*4+1],
                                       raw.Rotations[i*4+2], raw.Rotations[i*4+3]);
                WriteUInt(otherBytes, off, PackRotation(q));
                WriteFloat(otherBytes, off + 4,  raw.Scales[i*3]);
                WriteFloat(otherBytes, off + 8,  raw.Scales[i*3+1]);
                WriteFloat(otherBytes, off + 12, raw.Scales[i*3+2]);
            }

            // === 컬러 텍스처 (ColorFormat.Float32x4, Morton-swizzled, 16 bytes/pixel) ===
            int texH        = CalcTexHeight(n);
            int totalPixels = TEX_W * texH;
            byte[] colorBytes = new byte[totalPixels * 16];
            for (int i = 0; i < n; i++)
            {
                int dst = MortonIndex(i) * 16;
                int src = i * 4;
                WriteFloat(colorBytes, dst,      raw.Colors[src]);
                WriteFloat(colorBytes, dst + 4,  raw.Colors[src + 1]);
                WriteFloat(colorBytes, dst + 8,  raw.Colors[src + 2]);
                WriteFloat(colorBytes, dst + 12, raw.Colors[src + 3]);
            }

            // === SH 데이터 (SHTableItemFloat32, 192 bytes/splat = 48 floats) ===
            var shFmt = raw.HasSH ? GaussianSplatAsset.SHFormat.Float32
                                   : GaussianSplatAsset.SHFormat.Norm6;
            byte[] shBytes;
            if (raw.HasSH)
            {
                shBytes = new byte[n * 192];
                Buffer.BlockCopy(raw.SHCoeffs, 0, shBytes, 0, shBytes.Length);
            }
            else
            {
                shBytes = new byte[0];
            }

            // === 청크 데이터 (per-256-splat position bounds) ===
            byte[] chunkBytes = BuildChunkData(n, raw.Positions);

            // === GaussianSplatAsset 생성 (메인 스레드 전용) ===
            var asset = ScriptableObject.CreateInstance<GaussianSplatAsset>();
            asset.Initialize(n,
                GaussianSplatAsset.VectorFormat.Float32,
                GaussianSplatAsset.VectorFormat.Float32,
                GaussianSplatAsset.ColorFormat.Float32x4,
                shFmt,
                bMin, bMax,
                cameras: null);

            asset.SetAssetFiles(
                new TextAsset(chunkBytes),
                new TextAsset(posBytes),
                new TextAsset(otherBytes),
                new TextAsset(colorBytes),
                new TextAsset(shBytes));

            return asset;
        }

        // ── 청크 데이터 (64 bytes/chunk) ─────────────────────────────────────────

        private static byte[] BuildChunkData(int n, float[] positions)
        {
            int chunkCount = (n + 255) / 256;
            byte[] data    = new byte[chunkCount * 64];

            for (int c = 0; c < chunkCount; c++)
            {
                int start = c * 256;
                int end   = Math.Min(start + 256, n);

                float minX = float.MaxValue,  minY = float.MaxValue,  minZ = float.MaxValue;
                float maxX = float.MinValue, maxY = float.MinValue, maxZ = float.MinValue;
                for (int i = start; i < end; i++)
                {
                    float x = positions[i*3], y = positions[i*3+1], z = positions[i*3+2];
                    if (x < minX) minX = x;  if (x > maxX) maxX = x;
                    if (y < minY) minY = y;  if (y > maxY) maxY = y;
                    if (z < minZ) minZ = z;  if (z > maxZ) maxZ = z;
                }

                int off = c * 64;
                // colR/G/B/A (offset 0-15) = 0 for Float32 format
                WriteFloat(data, off + 16, minX);  WriteFloat(data, off + 20, maxX);
                WriteFloat(data, off + 24, minY);  WriteFloat(data, off + 28, maxY);
                WriteFloat(data, off + 32, minZ);  WriteFloat(data, off + 36, maxZ);
                // sclX/Y/Z, shR/G/B (offset 40-63) = 0
            }
            return data;
        }

        // ── 회전 패킹 (Smallest-Three, 10-10-10-2 bits) ──────────────────────────

        private static uint PackRotation(Quaternion q)
        {
            float len = Mathf.Sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w);
            if (len > 1e-6f) { q.x /= len; q.y /= len; q.z /= len; q.w /= len; }

            float[] c = { q.x, q.y, q.z, q.w };
            int maxIdx = 0;
            for (int i = 1; i < 4; i++)
                if (Mathf.Abs(c[i]) > Mathf.Abs(c[maxIdx])) maxIdx = i;

            float sign = c[maxIdx] >= 0f ? 1f : -1f;
            const float range = 0.70710678118f;
            uint[] enc = new uint[3];
            int j = 0;
            for (int i = 0; i < 4; i++)
            {
                if (i == maxIdx) continue;
                enc[j++] = (uint)Mathf.Clamp(Mathf.RoundToInt((c[i]*sign / range + 1f) * 511.5f), 0, 1023);
            }
            return ((uint)maxIdx << 30) | (enc[0] << 20) | (enc[1] << 10) | enc[2];
        }

        // ── Morton 스위즐 ─────────────────────────────────────────────────────────

        private static int CalcTexHeight(int n)
        {
            int h = Math.Max(1, (n + TEX_W - 1) / TEX_W);
            return (h + 15) / 16 * 16;
        }

        private static int MortonIndex(int idx)
        {
            int x = idx % TEX_W, y = idx / TEX_W;
            int tx = x / 16, ty = y / 16;
            int lx = x % 16, ly = y % 16;
            return (ty * (TEX_W / 16) + tx) * 256 + Morton2D(lx, ly);
        }

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

        // ── 바이트 쓰기 ───────────────────────────────────────────────────────────

        private static void WriteFloat(byte[] buf, int off, float v)
        {
            var b = BitConverter.GetBytes(v);
            buf[off] = b[0]; buf[off+1] = b[1]; buf[off+2] = b[2]; buf[off+3] = b[3];
        }

        private static void WriteUInt(byte[] buf, int off, uint v)
        {
            buf[off] = (byte)v; buf[off+1] = (byte)(v>>8);
            buf[off+2] = (byte)(v>>16); buf[off+3] = (byte)(v>>24);
        }

        // ── 리플렉션 ──────────────────────────────────────────────────────────────

        private static void SetField(object obj, string name, object value)
        {
            var f = obj.GetType().GetField(name,
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            if (f != null) f.SetValue(obj, value);
            else Debug.LogWarning($"[UnityGSLoader] Field '{name}' not found in {obj.GetType().Name}");
        }
    }
}
