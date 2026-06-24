using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace GaussianSplatting
{
    /// <summary>
    /// iOS/Android 네이티브 갤러리 접근 (간단한 구현)
    /// </summary>
    public static class NativeGallery
    {
        public enum Permission
        {
            Denied = 0,
            Granted = 1,
            ShouldAsk = 2
        }

        public delegate void PickVideoCallback(string path);

        private static PickVideoCallback pickVideoCallback;

#if UNITY_IOS && !UNITY_EDITOR
        [DllImport("__Internal")]
        private static extern void _PickVideo();

        [DllImport("__Internal")]
        private static extern int _CheckPermission();

        [DllImport("__Internal")]
        private static extern int _RequestPermission();
#endif

        /// <summary>
        /// 비디오 선택
        /// </summary>
        public static void PickVideo(PickVideoCallback callback)
        {
            pickVideoCallback = callback;

#if UNITY_IOS && !UNITY_EDITOR
            Debug.Log("[NativeGallery] Opening iOS photo library...");
            _PickVideo();
#elif UNITY_ANDROID && !UNITY_EDITOR
            Debug.Log("[NativeGallery] Opening Android gallery...");
            PickVideoAndroid();
#else
            Debug.LogWarning("[NativeGallery] Not supported in editor/this platform");
            callback?.Invoke(null);
#endif
        }

        /// <summary>
        /// 권한 확인
        /// </summary>
        public static Permission CheckPermission()
        {
#if UNITY_IOS && !UNITY_EDITOR
            return (Permission)_CheckPermission();
#elif UNITY_ANDROID && !UNITY_EDITOR
            return Permission.Granted; // Android는 간단히 처리
#else
            return Permission.Granted;
#endif
        }

        /// <summary>
        /// 권한 요청
        /// </summary>
        public static Permission RequestPermission()
        {
#if UNITY_IOS && !UNITY_EDITOR
            return (Permission)_RequestPermission();
#elif UNITY_ANDROID && !UNITY_EDITOR
            return Permission.Granted;
#else
            return Permission.Granted;
#endif
        }

        /// <summary>
        /// iOS 네이티브 콜백 (네이티브 코드에서 호출)
        /// </summary>
        public static void OnVideoPickedIOS(string path)
        {
            Debug.Log($"[NativeGallery] Video picked: {path}");
            pickVideoCallback?.Invoke(path);
            pickVideoCallback = null;
        }

        /// <summary>
        /// Android 갤러리 (간단한 Intent 방식)
        /// </summary>
        private static void PickVideoAndroid()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                AndroidJavaClass unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
                AndroidJavaObject currentActivity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity");

                AndroidJavaObject intent = new AndroidJavaObject("android.content.Intent");
                intent.Call<AndroidJavaObject>("setAction", "android.intent.action.PICK");
                intent.Call<AndroidJavaObject>("setType", "video/*");

                currentActivity.Call("startActivityForResult", intent, 1);

                Debug.Log("[NativeGallery] Android intent started");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[NativeGallery] Android error: {ex.Message}");
                pickVideoCallback?.Invoke(null);
                pickVideoCallback = null;
            }
#endif
        }
    }
}
