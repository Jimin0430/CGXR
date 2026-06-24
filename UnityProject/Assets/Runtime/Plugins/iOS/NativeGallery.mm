#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <Photos/Photos.h>
#import <PhotosUI/PhotosUI.h>
// kUTTypeMovie removed in newer SDKs; use raw UTI string "public.movie" instead

// Unity 콜백 함수
extern "C" {
    void UnitySendMessage(const char* obj, const char* method, const char* msg);
}

@interface NativeGalleryController : UIViewController <UINavigationControllerDelegate, UIImagePickerControllerDelegate>
@end

@implementation NativeGalleryController

static NativeGalleryController* instance = nil;

+ (NativeGalleryController*)getInstance {
    if (instance == nil) {
        instance = [[NativeGalleryController alloc] init];
    }
    return instance;
}

// 비디오 선택
- (void)pickVideo {
    NSLog(@"[NativeGallery] pickVideo called");

    dispatch_async(dispatch_get_main_queue(), ^{
        UIImagePickerController* picker = [[UIImagePickerController alloc] init];
        picker.delegate = self;
        picker.sourceType = UIImagePickerControllerSourceTypePhotoLibrary;
        picker.mediaTypes = @[@"public.movie"];
        picker.videoQuality = UIImagePickerControllerQualityTypeHigh;
        picker.allowsEditing = NO;

        UIViewController* rootVC = UnityGetGLViewController();
        [rootVC presentViewController:picker animated:YES completion:nil];

        NSLog(@"[NativeGallery] Picker presented");
    });
}

// 비디오 선택 완료 콜백
- (void)imagePickerController:(UIImagePickerController*)picker didFinishPickingMediaWithInfo:(NSDictionary<UIImagePickerControllerInfoKey, id>*)info {
    NSLog(@"[NativeGallery] Video picked");

    NSURL* videoURL = info[UIImagePickerControllerMediaURL];

    [picker dismissViewControllerAnimated:YES completion:nil];

    if (!videoURL) {
        NSLog(@"[NativeGallery] No video URL");
        UnitySendMessage("VideoUploadSetup", "OnVideoPickedIOS", "");
        return;
    }

    // UIImagePickerController의 임시 파일은 picker 해제 후 삭제될 수 있어서
    // 앱 캐시 디렉토리에 복사한 뒤 Unity에 전달한다
    NSString* cacheDir = [NSSearchPathForDirectoriesInDomains(NSCachesDirectory, NSUserDomainMask, YES) firstObject];
    NSString* filename = [NSString stringWithFormat:@"cgxr_video_%lld.mov",
                          (long long)([[NSDate date] timeIntervalSince1970] * 1000)];
    NSString* destPath = [cacheDir stringByAppendingPathComponent:filename];
    NSURL* destURL = [NSURL fileURLWithPath:destPath];

    NSError* error = nil;
    [[NSFileManager defaultManager] copyItemAtURL:videoURL toURL:destURL error:&error];

    if (!error) {
        NSLog(@"[NativeGallery] Video copied to: %@", destPath);
        UnitySendMessage("VideoUploadSetup", "OnVideoPickedIOS", [destPath UTF8String]);
    } else {
        // 복사 실패 시 원본 경로로 시도
        NSLog(@"[NativeGallery] Copy failed (%@), using original path", error.localizedDescription);
        UnitySendMessage("VideoUploadSetup", "OnVideoPickedIOS", [[videoURL path] UTF8String]);
    }
}

// 취소
- (void)imagePickerControllerDidCancel:(UIImagePickerController*)picker {
    NSLog(@"[NativeGallery] Picker cancelled");
    [picker dismissViewControllerAnimated:YES completion:nil];
    UnitySendMessage("VideoUploadSetup", "OnVideoPickedIOS", "");
}

@end

// C 인터페이스
extern "C" {
    // 비디오 선택
    void _PickVideo() {
        [[NativeGalleryController getInstance] pickVideo];
    }

    // 권한 확인
    int _CheckPermission() {
        PHAuthorizationStatus status = [PHPhotoLibrary authorizationStatus];

        switch (status) {
            case PHAuthorizationStatusAuthorized:
                return 1; // Granted
            case PHAuthorizationStatusDenied:
            case PHAuthorizationStatusRestricted:
                return 0; // Denied
            case PHAuthorizationStatusNotDetermined:
                return 2; // ShouldAsk
            default:
                return 0;
        }
    }

    // 권한 요청
    int _RequestPermission() {
        __block int result = 0;

        dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);

        [PHPhotoLibrary requestAuthorization:^(PHAuthorizationStatus status) {
            switch (status) {
                case PHAuthorizationStatusAuthorized:
                    result = 1;
                    break;
                case PHAuthorizationStatusDenied:
                case PHAuthorizationStatusRestricted:
                    result = 0;
                    break;
                default:
                    result = 2;
                    break;
            }
            dispatch_semaphore_signal(semaphore);
        }];

        dispatch_semaphore_wait(semaphore, DISPATCH_TIME_FOREVER);
        return result;
    }
}
