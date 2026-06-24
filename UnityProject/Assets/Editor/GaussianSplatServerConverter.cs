// SPDX-License-Identifier: MIT
// 서버 배치 모드에서 PLY → .bytes 변환
// 실행: Unity -batchmode -quit -projectPath <proj> -executeMethod GaussianSplatting.ServerConverter.GaussianSplatServerConverter.ConvertPLY -inputPLY <ply> -outputDir <dir> [-quality Medium]

using System;
using System.Collections.Generic;
using System.IO;
using GaussianSplatting.Editor.Utils;
using GaussianSplatting.Runtime;
using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEditor;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace GaussianSplatting.ServerConverter
{
    [BurstCompile]
    public static class GaussianSplatServerConverter
    {
        [MenuItem("Server/Convert PLY")]
        public static void ConvertPLY()
        {
            string inputPath = GetArg("-inputPLY");
            string outputDir  = GetArg("-outputDir");
            string quality    = GetArg("-quality", "Medium");

            if (string.IsNullOrEmpty(inputPath) || string.IsNullOrEmpty(outputDir))
            {
                Debug.LogError("Usage: -inputPLY <path> -outputDir <path> [-quality VeryLow|Low|Medium|High|VeryHigh]");
                EditorApplication.Exit(1);
                return;
            }

            try
            {
                ConvertPLYFile(inputPath, outputDir, quality);
                Debug.Log($"Conversion OK: {inputPath} -> {outputDir}");
                EditorApplication.Exit(0);
            }
            catch (Exception ex)
            {
                Debug.LogError($"Conversion FAILED: {ex.Message}\n{ex.StackTrace}");
                EditorApplication.Exit(1);
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // 메인 변환 파이프라인
        // ─────────────────────────────────────────────────────────────────────

        static unsafe void ConvertPLYFile(string inputPath, string outputDir, string qualityStr)
        {
            ParseQuality(qualityStr, out var fmtPos, out var fmtScale, out var fmtColor, out var fmtSH);

            Debug.Log($"Reading PLY: {inputPath}");
            GaussianFileReader.ReadFile(inputPath, out NativeArray<InputSplatData> inputSplats);
            using (inputSplats)
            {
                if (inputSplats.Length == 0)
                    throw new Exception("PLY file is empty or failed to read");

                Debug.Log($"Loaded {inputSplats.Length:N0} splats");

                // 1. Bounds
                float3 boundsMin, boundsMax;
                var boundsJob = new CalcBoundsJob
                {
                    m_BoundsMin = &boundsMin,
                    m_BoundsMax = &boundsMax,
                    m_SplatData = inputSplats
                };
                boundsJob.Schedule().Complete();
                Debug.Log($"Bounds: {boundsMin} .. {boundsMax}");

                // 2. Morton 재정렬
                Debug.Log("Morton reordering...");
                ReorderMorton(inputSplats, boundsMin, boundsMax);

                // 3. SH 클러스터링 (옵션)
                NativeArray<int> splatSHIndices = default;
                NativeArray<GaussianSplatAsset.SHTableItemFloat16> clusteredSHs = default;
                if (fmtSH >= GaussianSplatAsset.SHFormat.Cluster64k)
                {
                    Debug.Log("Clustering SHs...");
                    ClusterSHs(inputSplats, fmtSH, out clusteredSHs, out splatSHIndices);
                }

                // 4. 출력 파일 생성
                Directory.CreateDirectory(outputDir);
                string baseName  = Path.GetFileNameWithoutExtension(inputPath);
                string pathChunk = Path.Combine(outputDir, $"{baseName}_chk.bytes");
                string pathPos   = Path.Combine(outputDir, $"{baseName}_pos.bytes");
                string pathOther = Path.Combine(outputDir, $"{baseName}_oth.bytes");
                string pathCol   = Path.Combine(outputDir, $"{baseName}_col.bytes");
                string pathSh    = Path.Combine(outputDir, $"{baseName}_shs.bytes");
                string pathMeta  = Path.Combine(outputDir, $"{baseName}_meta.json");

                var dataHash = new Hash128((uint)inputSplats.Length, (uint)GaussianSplatAsset.kCurrentVersion, 0, 0);
                bool useChunks = IsUsingChunks(fmtPos, fmtScale, fmtColor, fmtSH);

                if (useChunks)
                {
                    Debug.Log("Creating chunk data...");
                    CreateChunkData(inputSplats, pathChunk, ref dataHash);
                }
                Debug.Log("Creating position data...");
                CreatePositionsData(inputSplats, pathPos, ref dataHash, fmtPos);
                Debug.Log("Creating other data...");
                CreateOtherData(inputSplats, pathOther, ref dataHash, fmtScale, splatSHIndices);
                Debug.Log("Creating color data...");
                CreateColorData(inputSplats, pathCol, ref dataHash, fmtColor);
                Debug.Log("Creating SH data...");
                CreateSHData(inputSplats, pathSh, ref dataHash, fmtSH, clusteredSHs);

                if (splatSHIndices.IsCreated) splatSHIndices.Dispose();
                if (clusteredSHs.IsCreated)   clusteredSHs.Dispose();

                // 5. 메타데이터 (모바일 클라이언트가 읽을 JSON)
                var meta = new ConversionMetadata
                {
                    splatCount    = inputSplats.Length,
                    formatVersion = GaussianSplatAsset.kCurrentVersion,
                    posFormat     = (int)fmtPos,
                    scaleFormat   = (int)fmtScale,
                    colorFormat   = (int)fmtColor,
                    shFormat      = (int)fmtSH,
                    boundsMin     = new[] { boundsMin.x, boundsMin.y, boundsMin.z },
                    boundsMax     = new[] { boundsMax.x, boundsMax.y, boundsMax.z },
                    dataHash      = dataHash.ToString(),
                    hasChunks     = useChunks
                };
                File.WriteAllText(pathMeta, JsonUtility.ToJson(meta, true));

                Debug.Log($"Output files written to: {outputDir}");
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Bounds 계산
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct CalcBoundsJob : IJob
        {
            [NativeDisableUnsafePtrRestriction] public unsafe float3* m_BoundsMin;
            [NativeDisableUnsafePtrRestriction] public unsafe float3* m_BoundsMax;
            [ReadOnly] public NativeArray<InputSplatData> m_SplatData;

            public unsafe void Execute()
            {
                float3 bMin = float.PositiveInfinity;
                float3 bMax = float.NegativeInfinity;
                for (int i = 0; i < m_SplatData.Length; ++i)
                {
                    float3 pos = m_SplatData[i].pos;
                    bMin = math.min(bMin, pos);
                    bMax = math.max(bMax, pos);
                }
                *m_BoundsMin = bMin;
                *m_BoundsMax = bMax;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Morton 재정렬
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct ReorderMortonJob : IJobParallelFor
        {
            const float kScaler = (float)((1 << 21) - 1);
            public float3 m_BoundsMin;
            public float3 m_InvBoundsSize;
            [ReadOnly] public NativeArray<InputSplatData> m_SplatData;
            public NativeArray<(ulong, int)> m_Order;

            public void Execute(int index)
            {
                float3 pos = ((float3)m_SplatData[index].pos - m_BoundsMin) * m_InvBoundsSize * kScaler;
                uint3 ipos = (uint3)pos;
                ulong code = GaussianUtils.MortonEncode3(ipos);
                m_Order[index] = (code, index);
            }
        }

        struct OrderComparer : IComparer<(ulong, int)>
        {
            public int Compare((ulong, int) a, (ulong, int) b)
            {
                if (a.Item1 < b.Item1) return -1;
                if (a.Item1 > b.Item1) return +1;
                return a.Item2 - b.Item2;
            }
        }

        static void ReorderMorton(NativeArray<InputSplatData> splatData, float3 boundsMin, float3 boundsMax)
        {
            var orderJob = new ReorderMortonJob
            {
                m_SplatData      = splatData,
                m_BoundsMin      = boundsMin,
                m_InvBoundsSize  = 1.0f / (boundsMax - boundsMin),
                m_Order          = new NativeArray<(ulong, int)>(splatData.Length, Allocator.TempJob)
            };
            orderJob.Schedule(splatData.Length, 4096).Complete();
            orderJob.m_Order.Sort(new OrderComparer());

            NativeArray<InputSplatData> copy = new(orderJob.m_SplatData, Allocator.TempJob);
            for (int i = 0; i < copy.Length; ++i)
                orderJob.m_SplatData[i] = copy[orderJob.m_Order[i].Item2];
            copy.Dispose();
            orderJob.m_Order.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // SH 클러스터링 (Cluster* 포맷일 때만 사용)
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        static unsafe void GatherSHs(int splatCount, InputSplatData* splatData, float* shData)
        {
            for (int i = 0; i < splatCount; ++i)
            {
                // InputSplatData에서 sh1 오프셋 = 9 floats (pos+nor+dc0)
                UnsafeUtility.MemCpy(shData, ((float*)splatData) + 9, 15 * 3 * sizeof(float));
                splatData++;
                shData += 15 * 3;
            }
        }

        [BurstCompile]
        struct ConvertSHClustersJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> m_Input;
            public NativeArray<GaussianSplatAsset.SHTableItemFloat16> m_Output;

            public void Execute(int index)
            {
                int addr = index * 15;
                GaussianSplatAsset.SHTableItemFloat16 res;
                res.sh1 = new half3(m_Input[addr + 0]);  res.sh2 = new half3(m_Input[addr + 1]);
                res.sh3 = new half3(m_Input[addr + 2]);  res.sh4 = new half3(m_Input[addr + 3]);
                res.sh5 = new half3(m_Input[addr + 4]);  res.sh6 = new half3(m_Input[addr + 5]);
                res.sh7 = new half3(m_Input[addr + 6]);  res.sh8 = new half3(m_Input[addr + 7]);
                res.sh9 = new half3(m_Input[addr + 8]);  res.shA = new half3(m_Input[addr + 9]);
                res.shB = new half3(m_Input[addr + 10]); res.shC = new half3(m_Input[addr + 11]);
                res.shD = new half3(m_Input[addr + 12]); res.shE = new half3(m_Input[addr + 13]);
                res.shF = new half3(m_Input[addr + 14]); res.shPadding = default;
                m_Output[index] = res;
            }
        }

        static bool LogClusterProgress(float val)
        {
            Debug.Log($"  SH clustering: {val:P0}");
            return true;
        }

        static unsafe void ClusterSHs(
            NativeArray<InputSplatData> splatData,
            GaussianSplatAsset.SHFormat format,
            out NativeArray<GaussianSplatAsset.SHTableItemFloat16> shs,
            out NativeArray<int> shIndices)
        {
            shs = default;
            shIndices = default;

            int shCount = GaussianSplatAsset.GetSHCount(format, splatData.Length);
            if (shCount >= splatData.Length) return; // 클러스터 불필요

            const int kShDim    = 15 * 3;
            const int kBatch    = 2048;
            float passes = format switch
            {
                GaussianSplatAsset.SHFormat.Cluster64k => 0.3f,
                GaussianSplatAsset.SHFormat.Cluster32k => 0.4f,
                GaussianSplatAsset.SHFormat.Cluster16k => 0.5f,
                GaussianSplatAsset.SHFormat.Cluster8k  => 0.8f,
                GaussianSplatAsset.SHFormat.Cluster4k  => 1.2f,
                _ => throw new ArgumentOutOfRangeException(nameof(format))
            };

            NativeArray<float> shData  = new(splatData.Length * kShDim, Allocator.Persistent);
            GatherSHs(splatData.Length, (InputSplatData*)splatData.GetUnsafeReadOnlyPtr(), (float*)shData.GetUnsafePtr());

            NativeArray<float> shMeans = new(shCount * kShDim, Allocator.Persistent);
            shIndices = new(splatData.Length, Allocator.Persistent);

            KMeansClustering.Calculate(kShDim, shData, kBatch, passes, LogClusterProgress, shMeans, shIndices);
            shData.Dispose();

            shs = new NativeArray<GaussianSplatAsset.SHTableItemFloat16>(shCount, Allocator.Persistent);
            new ConvertSHClustersJob
            {
                m_Input  = shMeans.Reinterpret<float3>(4),
                m_Output = shs
            }.Schedule(shCount, 256).Complete();
            shMeans.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // Chunk 데이터 (압축 포맷 사용 시 per-256-splat min/max 바운드)
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct CalcChunkDataJob : IJobParallelFor
        {
            [NativeDisableParallelForRestriction] public NativeArray<InputSplatData> splatData;
            public NativeArray<GaussianSplatAsset.ChunkInfo> chunks;

            public void Execute(int chunkIdx)
            {
                float3 cMinPos = float.PositiveInfinity, cMaxPos = float.NegativeInfinity;
                float3 cMinScl = float.PositiveInfinity, cMaxScl = float.NegativeInfinity;
                float4 cMinCol = float.PositiveInfinity, cMaxCol = float.NegativeInfinity;
                float3 cMinShs = float.PositiveInfinity, cMaxShs = float.NegativeInfinity;

                int beg = math.min(chunkIdx * GaussianSplatAsset.kChunkSize, splatData.Length);
                int end = math.min((chunkIdx + 1) * GaussianSplatAsset.kChunkSize, splatData.Length);

                for (int i = beg; i < end; ++i)
                {
                    InputSplatData s = splatData[i];
                    s.scale   = math.pow(s.scale, 1.0f / 8.0f);
                    s.opacity = GaussianUtils.SquareCentered01(s.opacity);
                    splatData[i] = s;

                    cMinPos = math.min(cMinPos, s.pos); cMaxPos = math.max(cMaxPos, s.pos);
                    cMinScl = math.min(cMinScl, s.scale); cMaxScl = math.max(cMaxScl, s.scale);
                    float4 col = new float4(s.dc0, s.opacity);
                    cMinCol = math.min(cMinCol, col); cMaxCol = math.max(cMaxCol, col);
                    cMinShs = math.min(cMinShs, s.sh1); cMaxShs = math.max(cMaxShs, s.sh1);
                    cMinShs = math.min(cMinShs, s.sh2); cMaxShs = math.max(cMaxShs, s.sh2);
                    cMinShs = math.min(cMinShs, s.sh3); cMaxShs = math.max(cMaxShs, s.sh3);
                    cMinShs = math.min(cMinShs, s.sh4); cMaxShs = math.max(cMaxShs, s.sh4);
                    cMinShs = math.min(cMinShs, s.sh5); cMaxShs = math.max(cMaxShs, s.sh5);
                    cMinShs = math.min(cMinShs, s.sh6); cMaxShs = math.max(cMaxShs, s.sh6);
                    cMinShs = math.min(cMinShs, s.sh7); cMaxShs = math.max(cMaxShs, s.sh7);
                    cMinShs = math.min(cMinShs, s.sh8); cMaxShs = math.max(cMaxShs, s.sh8);
                    cMinShs = math.min(cMinShs, s.sh9); cMaxShs = math.max(cMaxShs, s.sh9);
                    cMinShs = math.min(cMinShs, s.shA); cMaxShs = math.max(cMaxShs, s.shA);
                    cMinShs = math.min(cMinShs, s.shB); cMaxShs = math.max(cMaxShs, s.shB);
                    cMinShs = math.min(cMinShs, s.shC); cMaxShs = math.max(cMaxShs, s.shC);
                    cMinShs = math.min(cMinShs, s.shD); cMaxShs = math.max(cMaxShs, s.shD);
                    cMinShs = math.min(cMinShs, s.shE); cMaxShs = math.max(cMaxShs, s.shE);
                    cMinShs = math.min(cMinShs, s.shF); cMaxShs = math.max(cMaxShs, s.shF);
                }

                cMaxPos = math.max(cMaxPos, cMinPos + 1e-5f);
                cMaxScl = math.max(cMaxScl, cMinScl + 1e-5f);
                cMaxCol = math.max(cMaxCol, cMinCol + 1e-5f);
                cMaxShs = math.max(cMaxShs, cMinShs + 1e-5f);

                GaussianSplatAsset.ChunkInfo info = default;
                info.posX = new float2(cMinPos.x, cMaxPos.x);
                info.posY = new float2(cMinPos.y, cMaxPos.y);
                info.posZ = new float2(cMinPos.z, cMaxPos.z);
                info.sclX = math.f32tof16(cMinScl.x) | (math.f32tof16(cMaxScl.x) << 16);
                info.sclY = math.f32tof16(cMinScl.y) | (math.f32tof16(cMaxScl.y) << 16);
                info.sclZ = math.f32tof16(cMinScl.z) | (math.f32tof16(cMaxScl.z) << 16);
                info.colR = math.f32tof16(cMinCol.x) | (math.f32tof16(cMaxCol.x) << 16);
                info.colG = math.f32tof16(cMinCol.y) | (math.f32tof16(cMaxCol.y) << 16);
                info.colB = math.f32tof16(cMinCol.z) | (math.f32tof16(cMaxCol.z) << 16);
                info.colA = math.f32tof16(cMinCol.w) | (math.f32tof16(cMaxCol.w) << 16);
                info.shR  = math.f32tof16(cMinShs.x) | (math.f32tof16(cMaxShs.x) << 16);
                info.shG  = math.f32tof16(cMinShs.y) | (math.f32tof16(cMaxShs.y) << 16);
                info.shB  = math.f32tof16(cMinShs.z) | (math.f32tof16(cMaxShs.z) << 16);
                chunks[chunkIdx] = info;

                // 데이터를 0..1 범위로 정규화
                for (int i = beg; i < end; ++i)
                {
                    InputSplatData s = splatData[i];
                    s.pos     = ((float3)s.pos   - cMinPos) / (cMaxPos - cMinPos);
                    s.scale   = ((float3)s.scale - cMinScl) / (cMaxScl - cMinScl);
                    s.dc0     = ((float3)s.dc0   - cMinCol.xyz) / (cMaxCol.xyz - cMinCol.xyz);
                    s.opacity = (s.opacity        - cMinCol.w)   / (cMaxCol.w   - cMinCol.w);
                    s.sh1 = ((float3)s.sh1 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh2 = ((float3)s.sh2 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh3 = ((float3)s.sh3 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh4 = ((float3)s.sh4 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh5 = ((float3)s.sh5 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh6 = ((float3)s.sh6 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh7 = ((float3)s.sh7 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh8 = ((float3)s.sh8 - cMinShs) / (cMaxShs - cMinShs);
                    s.sh9 = ((float3)s.sh9 - cMinShs) / (cMaxShs - cMinShs);
                    s.shA = ((float3)s.shA - cMinShs) / (cMaxShs - cMinShs);
                    s.shB = ((float3)s.shB - cMinShs) / (cMaxShs - cMinShs);
                    s.shC = ((float3)s.shC - cMinShs) / (cMaxShs - cMinShs);
                    s.shD = ((float3)s.shD - cMinShs) / (cMaxShs - cMinShs);
                    s.shE = ((float3)s.shE - cMinShs) / (cMaxShs - cMinShs);
                    s.shF = ((float3)s.shF - cMinShs) / (cMaxShs - cMinShs);
                    splatData[i] = s;
                }
            }
        }

        static void CreateChunkData(NativeArray<InputSplatData> splatData, string filePath, ref Hash128 dataHash)
        {
            int chunkCount = (splatData.Length + GaussianSplatAsset.kChunkSize - 1) / GaussianSplatAsset.kChunkSize;
            var job = new CalcChunkDataJob
            {
                splatData = splatData,
                chunks    = new NativeArray<GaussianSplatAsset.ChunkInfo>(chunkCount, Allocator.TempJob)
            };
            job.Schedule(chunkCount, 8).Complete();
            dataHash.Append(ref job.chunks);
            using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            fs.Write(job.chunks.Reinterpret<byte>(UnsafeUtility.SizeOf<GaussianSplatAsset.ChunkInfo>()));
            job.chunks.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // 인코딩 헬퍼
        // ─────────────────────────────────────────────────────────────────────

        static ulong  EncodeFloat3ToNorm16(float3 v) =>
            (ulong)(v.x * 65535.5f) | ((ulong)(v.y * 65535.5f) << 16) | ((ulong)(v.z * 65535.5f) << 32);

        static uint   EncodeFloat3ToNorm11(float3 v) =>
            (uint)(v.x * 2047.5f) | ((uint)(v.y * 1023.5f) << 11) | ((uint)(v.z * 2047.5f) << 21);

        static ushort EncodeFloat3ToNorm655(float3 v) =>
            (ushort)((uint)(v.x * 63.5f) | ((uint)(v.y * 31.5f) << 6) | ((uint)(v.z * 31.5f) << 11));

        static ushort EncodeFloat3ToNorm565(float3 v) =>
            (ushort)((uint)(v.x * 31.5f) | ((uint)(v.y * 63.5f) << 5) | ((uint)(v.z * 31.5f) << 11));

        static uint   EncodeQuatToNorm10(float4 v) =>
            (uint)(v.x * 1023.5f) | ((uint)(v.y * 1023.5f) << 10) | ((uint)(v.z * 1023.5f) << 20) | ((uint)(v.w * 3.5f) << 30);

        static unsafe void EmitEncodedVector(float3 v, byte* ptr, GaussianSplatAsset.VectorFormat fmt)
        {
            switch (fmt)
            {
                case GaussianSplatAsset.VectorFormat.Float32:
                    *(float*)ptr = v.x; *(float*)(ptr + 4) = v.y; *(float*)(ptr + 8) = v.z;
                    break;
                case GaussianSplatAsset.VectorFormat.Norm16:
                    ulong e16 = EncodeFloat3ToNorm16(math.saturate(v));
                    *(uint*)ptr = (uint)e16; *(ushort*)(ptr + 4) = (ushort)(e16 >> 32);
                    break;
                case GaussianSplatAsset.VectorFormat.Norm11:
                    *(uint*)ptr = EncodeFloat3ToNorm11(math.saturate(v));
                    break;
                case GaussianSplatAsset.VectorFormat.Norm6:
                    *(ushort*)ptr = EncodeFloat3ToNorm655(math.saturate(v));
                    break;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // 위치 데이터
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct CreatePositionsDataJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<InputSplatData> m_Input;
            public GaussianSplatAsset.VectorFormat m_Format;
            public int m_FormatSize;
            [NativeDisableParallelForRestriction] public NativeArray<byte> m_Output;

            public unsafe void Execute(int index)
            {
                byte* ptr = (byte*)m_Output.GetUnsafePtr() + index * m_FormatSize;
                EmitEncodedVector(m_Input[index].pos, ptr, m_Format);
            }
        }

        static int NextMultipleOf(int size, int mul) => (size + mul - 1) / mul * mul;

        static void CreatePositionsData(NativeArray<InputSplatData> splats, string filePath,
            ref Hash128 dataHash, GaussianSplatAsset.VectorFormat fmtPos)
        {
            int fmtSize = GaussianSplatAsset.GetVectorSize(fmtPos);
            int dataLen = NextMultipleOf(splats.Length * fmtSize, 8);
            NativeArray<byte> data = new(dataLen, Allocator.TempJob);
            new CreatePositionsDataJob
            {
                m_Input = splats, m_Format = fmtPos, m_FormatSize = fmtSize, m_Output = data
            }.Schedule(splats.Length, 8192).Complete();
            dataHash.Append(data);
            using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            fs.Write(data);
            data.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // 회전 + 스케일 + SH 인덱스 데이터
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct CreateOtherDataJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<InputSplatData> m_Input;
            [NativeDisableContainerSafetyRestriction][ReadOnly] public NativeArray<int> m_SplatSHIndices;
            public GaussianSplatAsset.VectorFormat m_ScaleFormat;
            public int m_FormatSize;
            [NativeDisableParallelForRestriction] public NativeArray<byte> m_Output;

            public unsafe void Execute(int index)
            {
                byte* ptr = (byte*)m_Output.GetUnsafePtr() + index * m_FormatSize;
                Quaternion q = m_Input[index].rot;
                *(uint*)ptr = EncodeQuatToNorm10(new float4(q.x, q.y, q.z, q.w));
                ptr += 4;
                EmitEncodedVector(m_Input[index].scale, ptr, m_ScaleFormat);
                ptr += GaussianSplatAsset.GetVectorSize(m_ScaleFormat);
                if (m_SplatSHIndices.IsCreated)
                    *(ushort*)ptr = (ushort)m_SplatSHIndices[index];
            }
        }

        static void CreateOtherData(NativeArray<InputSplatData> splats, string filePath,
            ref Hash128 dataHash, GaussianSplatAsset.VectorFormat fmtScale, NativeArray<int> shIndices)
        {
            int fmtSize = GaussianSplatAsset.GetOtherSizeNoSHIndex(fmtScale);
            if (shIndices.IsCreated) fmtSize += 2;
            int dataLen = NextMultipleOf(splats.Length * fmtSize, 8);
            NativeArray<byte> data = new(dataLen, Allocator.TempJob);
            new CreateOtherDataJob
            {
                m_Input = splats, m_SplatSHIndices = shIndices,
                m_ScaleFormat = fmtScale, m_FormatSize = fmtSize, m_Output = data
            }.Schedule(splats.Length, 8192).Complete();
            dataHash.Append(data);
            using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            fs.Write(data);
            data.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // 컬러 텍스처 데이터 (Morton 스와이즐 적용)
        // ─────────────────────────────────────────────────────────────────────

        static int SplatIndexToTextureIndex(uint idx)
        {
            uint2 xy    = GaussianUtils.DecodeMorton2D_16x16(idx);
            uint width  = GaussianSplatAsset.kTextureWidth / 16;
            idx >>= 8;
            uint x = (idx % width) * 16 + xy.x;
            uint y = (idx / width) * 16 + xy.y;
            return (int)(y * GaussianSplatAsset.kTextureWidth + x);
        }

        [BurstCompile]
        struct CreateColorDataJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<InputSplatData> m_Input;
            [NativeDisableParallelForRestriction] public NativeArray<float4> m_Output;

            public void Execute(int index)
            {
                var splat = m_Input[index];
                int i = SplatIndexToTextureIndex((uint)index);
                m_Output[i] = new float4(splat.dc0.x, splat.dc0.y, splat.dc0.z, splat.opacity);
            }
        }

        [BurstCompile]
        struct ConvertColorJob : IJobParallelFor
        {
            public int width, height;
            [ReadOnly] public NativeArray<float4> inputData;
            [NativeDisableParallelForRestriction] public NativeArray<byte> outputData;
            public GaussianSplatAsset.ColorFormat format;
            public int formatBytesPerPixel;

            public unsafe void Execute(int y)
            {
                int srcIdx  = y * width;
                byte* dstPtr = (byte*)outputData.GetUnsafePtr() + y * width * formatBytesPerPixel;
                for (int x = 0; x < width; ++x)
                {
                    float4 pix = inputData[srcIdx];
                    switch (format)
                    {
                        case GaussianSplatAsset.ColorFormat.Float32x4:
                            *(float4*)dstPtr = pix; break;
                        case GaussianSplatAsset.ColorFormat.Float16x4:
                            *(half4*)dstPtr = new half4(pix); break;
                        case GaussianSplatAsset.ColorFormat.Norm8x4:
                            pix = math.saturate(pix);
                            *(uint*)dstPtr = (uint)(pix.x * 255.5f) | ((uint)(pix.y * 255.5f) << 8)
                                           | ((uint)(pix.z * 255.5f) << 16) | ((uint)(pix.w * 255.5f) << 24);
                            break;
                    }
                    srcIdx++;
                    dstPtr += formatBytesPerPixel;
                }
            }
        }

        static void CreateColorData(NativeArray<InputSplatData> splats, string filePath,
            ref Hash128 dataHash, GaussianSplatAsset.ColorFormat fmtColor)
        {
            var (width, height) = GaussianSplatAsset.CalcTextureSize(splats.Length);
            NativeArray<float4> data = new(width * height, Allocator.TempJob);
            new CreateColorDataJob { m_Input = splats, m_Output = data }.Schedule(splats.Length, 8192).Complete();

            dataHash.Append(data);
            dataHash.Append((int)fmtColor);

            GraphicsFormat gfxFmt = GaussianSplatAsset.ColorFormatToGraphics(fmtColor);
            int dstSize = (int)GraphicsFormatUtility.ComputeMipmapSize(width, height, gfxFmt);

            if (GraphicsFormatUtility.IsCompressedFormat(gfxFmt))
            {
                // BC7 등 압축 포맷 — EditorUtility.CompressTexture 사용 (배치 모드에서 동작)
                Texture2D tex = new Texture2D(width, height, GraphicsFormat.R32G32B32A32_SFloat,
                    TextureCreationFlags.DontInitializePixels | TextureCreationFlags.DontUploadUponCreate);
                tex.SetPixelData(data, 0);
                EditorUtility.CompressTexture(tex, GraphicsFormatUtility.GetTextureFormat(gfxFmt), 100);
                NativeArray<byte> cmpData = tex.GetPixelData<byte>(0);
                using var fsC = new FileStream(filePath, FileMode.Create, FileAccess.Write);
                fsC.Write(cmpData);
                UnityEngine.Object.DestroyImmediate(tex);
            }
            else
            {
                var jobConvert = new ConvertColorJob
                {
                    width = width, height = height,
                    inputData = data, format = fmtColor,
                    outputData = new NativeArray<byte>(dstSize, Allocator.TempJob),
                    formatBytesPerPixel = dstSize / width / height
                };
                jobConvert.Schedule(height, 1).Complete();
                using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
                fs.Write(jobConvert.outputData);
                jobConvert.outputData.Dispose();
            }
            data.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // SH (구면 조화 함수) 데이터
        // ─────────────────────────────────────────────────────────────────────

        [BurstCompile]
        struct CreateSHDataJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<InputSplatData> m_Input;
            public GaussianSplatAsset.SHFormat m_Format;
            public NativeArray<byte> m_Output;

            public unsafe void Execute(int index)
            {
                var s = m_Input[index];
                switch (m_Format)
                {
                    case GaussianSplatAsset.SHFormat.Float32:
                    {
                        GaussianSplatAsset.SHTableItemFloat32 res;
                        res.sh1 = s.sh1; res.sh2 = s.sh2; res.sh3 = s.sh3; res.sh4 = s.sh4; res.sh5 = s.sh5;
                        res.sh6 = s.sh6; res.sh7 = s.sh7; res.sh8 = s.sh8; res.sh9 = s.sh9; res.shA = s.shA;
                        res.shB = s.shB; res.shC = s.shC; res.shD = s.shD; res.shE = s.shE; res.shF = s.shF;
                        res.shPadding = default;
                        ((GaussianSplatAsset.SHTableItemFloat32*)m_Output.GetUnsafePtr())[index] = res;
                        break;
                    }
                    case GaussianSplatAsset.SHFormat.Float16:
                    {
                        GaussianSplatAsset.SHTableItemFloat16 res;
                        res.sh1 = new half3(s.sh1); res.sh2 = new half3(s.sh2); res.sh3 = new half3(s.sh3);
                        res.sh4 = new half3(s.sh4); res.sh5 = new half3(s.sh5); res.sh6 = new half3(s.sh6);
                        res.sh7 = new half3(s.sh7); res.sh8 = new half3(s.sh8); res.sh9 = new half3(s.sh9);
                        res.shA = new half3(s.shA); res.shB = new half3(s.shB); res.shC = new half3(s.shC);
                        res.shD = new half3(s.shD); res.shE = new half3(s.shE); res.shF = new half3(s.shF);
                        res.shPadding = default;
                        ((GaussianSplatAsset.SHTableItemFloat16*)m_Output.GetUnsafePtr())[index] = res;
                        break;
                    }
                    case GaussianSplatAsset.SHFormat.Norm11:
                    {
                        GaussianSplatAsset.SHTableItemNorm11 res;
                        res.sh1 = EncodeFloat3ToNorm11(s.sh1); res.sh2 = EncodeFloat3ToNorm11(s.sh2);
                        res.sh3 = EncodeFloat3ToNorm11(s.sh3); res.sh4 = EncodeFloat3ToNorm11(s.sh4);
                        res.sh5 = EncodeFloat3ToNorm11(s.sh5); res.sh6 = EncodeFloat3ToNorm11(s.sh6);
                        res.sh7 = EncodeFloat3ToNorm11(s.sh7); res.sh8 = EncodeFloat3ToNorm11(s.sh8);
                        res.sh9 = EncodeFloat3ToNorm11(s.sh9); res.shA = EncodeFloat3ToNorm11(s.shA);
                        res.shB = EncodeFloat3ToNorm11(s.shB); res.shC = EncodeFloat3ToNorm11(s.shC);
                        res.shD = EncodeFloat3ToNorm11(s.shD); res.shE = EncodeFloat3ToNorm11(s.shE);
                        res.shF = EncodeFloat3ToNorm11(s.shF);
                        ((GaussianSplatAsset.SHTableItemNorm11*)m_Output.GetUnsafePtr())[index] = res;
                        break;
                    }
                    case GaussianSplatAsset.SHFormat.Norm6:
                    {
                        GaussianSplatAsset.SHTableItemNorm6 res;
                        res.sh1 = EncodeFloat3ToNorm565(s.sh1); res.sh2 = EncodeFloat3ToNorm565(s.sh2);
                        res.sh3 = EncodeFloat3ToNorm565(s.sh3); res.sh4 = EncodeFloat3ToNorm565(s.sh4);
                        res.sh5 = EncodeFloat3ToNorm565(s.sh5); res.sh6 = EncodeFloat3ToNorm565(s.sh6);
                        res.sh7 = EncodeFloat3ToNorm565(s.sh7); res.sh8 = EncodeFloat3ToNorm565(s.sh8);
                        res.sh9 = EncodeFloat3ToNorm565(s.sh9); res.shA = EncodeFloat3ToNorm565(s.shA);
                        res.shB = EncodeFloat3ToNorm565(s.shB); res.shC = EncodeFloat3ToNorm565(s.shC);
                        res.shD = EncodeFloat3ToNorm565(s.shD); res.shE = EncodeFloat3ToNorm565(s.shE);
                        res.shF = EncodeFloat3ToNorm565(s.shF); res.shPadding = default;
                        ((GaussianSplatAsset.SHTableItemNorm6*)m_Output.GetUnsafePtr())[index] = res;
                        break;
                    }
                }
            }
        }

        static void EmitSimpleDataFile<T>(NativeArray<T> data, string filePath, ref Hash128 dataHash) where T : unmanaged
        {
            dataHash.Append(data);
            using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            fs.Write(data.Reinterpret<byte>(UnsafeUtility.SizeOf<T>()));
        }

        static void CreateSHData(NativeArray<InputSplatData> splats, string filePath,
            ref Hash128 dataHash, GaussianSplatAsset.SHFormat fmtSH,
            NativeArray<GaussianSplatAsset.SHTableItemFloat16> clusteredSHs)
        {
            if (clusteredSHs.IsCreated)
            {
                EmitSimpleDataFile(clusteredSHs, filePath, ref dataHash);
                return;
            }
            int dataLen = (int)GaussianSplatAsset.CalcSHDataSize(splats.Length, fmtSH);
            NativeArray<byte> data = new(dataLen, Allocator.TempJob);
            new CreateSHDataJob { m_Input = splats, m_Format = fmtSH, m_Output = data }
                .Schedule(splats.Length, 8192).Complete();
            EmitSimpleDataFile(data, filePath, ref dataHash);
            data.Dispose();
        }

        // ─────────────────────────────────────────────────────────────────────
        // 유틸
        // ─────────────────────────────────────────────────────────────────────

        static bool IsUsingChunks(GaussianSplatAsset.VectorFormat pos, GaussianSplatAsset.VectorFormat scale,
            GaussianSplatAsset.ColorFormat color, GaussianSplatAsset.SHFormat sh) =>
            pos   != GaussianSplatAsset.VectorFormat.Float32    ||
            scale != GaussianSplatAsset.VectorFormat.Float32    ||
            color != GaussianSplatAsset.ColorFormat.Float32x4   ||
            sh    != GaussianSplatAsset.SHFormat.Float32;

        static void ParseQuality(string quality,
            out GaussianSplatAsset.VectorFormat pos, out GaussianSplatAsset.VectorFormat scale,
            out GaussianSplatAsset.ColorFormat color, out GaussianSplatAsset.SHFormat sh)
        {
            switch (quality)
            {
                case "VeryLow":  // 18.6x 압축
                    pos = GaussianSplatAsset.VectorFormat.Norm11; scale = GaussianSplatAsset.VectorFormat.Norm6;
                    color = GaussianSplatAsset.ColorFormat.BC7;    sh = GaussianSplatAsset.SHFormat.Cluster4k;
                    break;
                case "Low":      // 14x 압축
                    pos = GaussianSplatAsset.VectorFormat.Norm11; scale = GaussianSplatAsset.VectorFormat.Norm6;
                    color = GaussianSplatAsset.ColorFormat.Norm8x4; sh = GaussianSplatAsset.SHFormat.Cluster16k;
                    break;
                case "Medium":   // 5x 압축 (기본값)
                    pos = GaussianSplatAsset.VectorFormat.Norm11; scale = GaussianSplatAsset.VectorFormat.Norm11;
                    color = GaussianSplatAsset.ColorFormat.Norm8x4; sh = GaussianSplatAsset.SHFormat.Norm6;
                    break;
                case "High":     // 3x 압축
                    pos = GaussianSplatAsset.VectorFormat.Norm16; scale = GaussianSplatAsset.VectorFormat.Norm16;
                    color = GaussianSplatAsset.ColorFormat.Float16x4; sh = GaussianSplatAsset.SHFormat.Norm11;
                    break;
                case "VeryHigh": // 무손실
                    pos = GaussianSplatAsset.VectorFormat.Float32; scale = GaussianSplatAsset.VectorFormat.Float32;
                    color = GaussianSplatAsset.ColorFormat.Float32x4; sh = GaussianSplatAsset.SHFormat.Float32;
                    break;
                default:
                    throw new ArgumentException($"Unknown quality: {quality}. Use VeryLow/Low/Medium/High/VeryHigh");
            }
        }

        static string GetArg(string name, string defaultValue = "")
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == name) return args[i + 1];
            return defaultValue;
        }

        // ─────────────────────────────────────────────────────────────────────
        // 메타데이터 (모바일 클라이언트에서 파싱)
        // ─────────────────────────────────────────────────────────────────────

        [Serializable]
        public class ConversionMetadata
        {
            public int      splatCount;
            public int      formatVersion;
            public int      posFormat;
            public int      scaleFormat;
            public int      colorFormat;
            public int      shFormat;
            public float[]  boundsMin;
            public float[]  boundsMax;
            public string   dataHash;
            public bool     hasChunks;
        }
    }
}
