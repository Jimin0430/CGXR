using UnityEngine;

namespace GaussianSplatting
{
    /// <summary>
    /// VideoUploadManager와 UI를 자동으로 연결하는 스크립트
    /// 씬에 이 GameObject만 추가하면 모든 UI가 자동 생성됩니다.
    /// </summary>
    public class VideoUploadSetup : MonoBehaviour
    {
        [Header("Server Configuration")]
        [SerializeField] private string serverUrl = "http://100.86.251.105:8000";
        [SerializeField] private string apiKey = "changeme";
        [SerializeField] private bool useSAM2 = true;
        [SerializeField] private float pollingInterval = 2f;

        private void Awake()
        {
            // 1. UI 생성
            AutoUIBuilder uiBuilder = gameObject.AddComponent<AutoUIBuilder>();

            // UI 생성이 완료될 때까지 대기 (같은 프레임에서 실행됨)
            StartCoroutine(SetupAfterUICreation(uiBuilder));
        }

        private System.Collections.IEnumerator SetupAfterUICreation(AutoUIBuilder uiBuilder)
        {
            // UI 생성 대기
            yield return null;

            // 2. VideoUploadManager 추가
            VideoUploadManager uploadManager = gameObject.AddComponent<VideoUploadManager>();

            // 3. UI 연결 (Reflection 사용)
            var uploadManagerType = typeof(VideoUploadManager);

            SetPrivateField(uploadManager, "serverUrl", serverUrl);
            SetPrivateField(uploadManager, "apiKey", apiKey);
            SetPrivateField(uploadManager, "uploadButton", uiBuilder.uploadButton);
            SetPrivateField(uploadManager, "statusText", uiBuilder.statusText);
            SetPrivateField(uploadManager, "progressBar", uiBuilder.progressBar);
            SetPrivateField(uploadManager, "logText", uiBuilder.logText);
            SetPrivateField(uploadManager, "useSAM2", useSAM2);
            SetPrivateField(uploadManager, "pollingInterval", pollingInterval);

            // 4. ServerConnectionTest 추가
            ServerConnectionTest serverTest = gameObject.AddComponent<ServerConnectionTest>();
            SetPrivateField(serverTest, "serverUrl", serverUrl);
            SetPrivateField(serverTest, "apiKey", apiKey);

            Debug.Log("[VideoUploadSetup] Setup complete! Press Play and click 'Upload Video' button.");
        }

        /// <summary>
        /// iOS 네이티브 갤러리 콜백 수신
        /// </summary>
        public void OnVideoPickedIOS(string path)
        {
            Debug.Log($"[VideoUploadSetup] iOS callback received: {path}");

            // NativeGallery의 콜백으로 전달
            if (!string.IsNullOrEmpty(path))
            {
                NativeGallery.OnVideoPickedIOS(path);
            }
            else
            {
                NativeGallery.OnVideoPickedIOS(null);
            }
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
                Debug.LogWarning($"[VideoUploadSetup] Field '{fieldName}' not found in {obj.GetType().Name}");
            }
        }
    }
}
