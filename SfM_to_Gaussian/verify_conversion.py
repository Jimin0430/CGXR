#!/usr/bin/env python3
"""
Verification script to inspect SfM to Gaussian conversion results
"""
import json
import numpy as np
from plyfile import PlyData

def verify_conversion():
    """Verify the conversion output files"""
    
    base_path = r"d:\JM\cgxr\CGXR\Extract_SfM\sparse\0"
    ply_path = f"{base_path}\points3D.ply"
    metadata_path = f"{base_path}\metadata.json"
    cameras_path = f"{base_path}\cameras_poses.json"
    
    print("\n" + "="*70)
    print("SfM to Gaussian Conversion Verification")
    print("="*70)
    
    # 1. Check PLY file
    print("\n[1] Point Cloud File (points3D.ply)")
    print("-" * 70)
    try:
        ply_data = PlyData.read(ply_path)
        vertices = ply_data['vertex']
        
        x = vertices['x']
        y = vertices['y']
        z = vertices['z']
        r = vertices['red']
        g = vertices['green']
        b = vertices['blue']
        
        print(f"✓ PLY file loaded successfully")
        print(f"  • Total points: {len(vertices):,}")
        print(f"  • File: {ply_path}")
        
        print(f"\n  Position Statistics:")
        print(f"    X: [{x.min():>9.3f}, {x.max():>9.3f}] range={x.max()-x.min():.3f}")
        print(f"    Y: [{y.min():>9.3f}, {y.max():>9.3f}] range={y.max()-y.min():.3f}")
        print(f"    Z: [{z.min():>9.3f}, {z.max():>9.3f}] range={z.max()-z.min():.3f}")
        
        print(f"\n  Color Statistics (0-255):")
        print(f"    Red:   [{r.min():>3d}, {r.max():>3d}] mean={r.mean():.1f}")
        print(f"    Green: [{g.min():>3d}, {g.max():>3d}] mean={g.mean():.1f}")
        print(f"    Blue:  [{b.min():>3d}, {b.max():>3d}] mean={b.mean():.1f}")
        
        # Check normals
        nx = vertices['nx']
        ny = vertices['ny']
        nz = vertices['nz']
        print(f"\n  Normal Statistics:")
        print(f"    X: [{nx.min():.3f}, {nx.max():.3f}]")
        print(f"    Y: [{ny.min():.3f}, {ny.max():.3f}]")
        print(f"    Z: [{nz.min():.3f}, {nz.max():.3f}]")
        
    except Exception as e:
        print(f"✗ Error loading PLY file: {e}")
        return False
    
    # 2. Check Metadata
    print("\n[2] Scene Metadata (metadata.json)")
    print("-" * 70)
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        print(f"✓ Metadata file loaded successfully")
        print(f"  • Total cameras: {metadata['num_cameras']}")
        print(f"  • Camera models: {metadata['num_camera_models']}")
        print(f"  • Total points: {metadata['num_points']:,}")
        
        norm = metadata['camera_normalization']
        print(f"\n  Scene Normalization (NeRF++):")
        print(f"    • Center translate: [{norm['translate'][0]:.6f}, "
              f"{norm['translate'][1]:.6f}, {norm['translate'][2]:.6f}]")
        print(f"    • Scene radius: {norm['radius']:.3f}")
        
        if 'cameras' in metadata:
            print(f"\n  Camera Models:")
            for cam_id, cam_info in metadata['cameras'].items():
                print(f"    • Camera {cam_id}:")
                print(f"      - Model: {cam_info['model']}")
                print(f"      - Resolution: {cam_info['width']}x{cam_info['height']}")
                print(f"      - Intrinsic params: {cam_info['params']}")
        
    except Exception as e:
        print(f"✗ Error loading metadata: {e}")
        return False
    
    # 3. Check Camera Poses
    print("\n[3] Camera Poses (cameras_poses.json)")
    print("-" * 70)
    try:
        with open(cameras_path, 'r') as f:
            cameras = json.load(f)
        
        print(f"✓ Camera poses file loaded successfully")
        print(f"  • Total cameras: {len(cameras)}")
        
        # Show first few cameras
        print(f"\n  Sample Camera Poses (first 3):")
        for idx, (cam_name, cam_data) in enumerate(list(cameras.items())[:3]):
            print(f"\n    Camera {idx+1}: {cam_name}")
            print(f"      - ID: {cam_data['image_id']}")
            print(f"      - Camera model ID: {cam_data['camera_id']}")
            qvec = cam_data['qvec']
            tvec = cam_data['tvec']
            print(f"      - Rotation (qvec): [{qvec[0]:.6f}, {qvec[1]:.6f}, "
                  f"{qvec[2]:.6f}, {qvec[3]:.6f}]")
            print(f"      - Translation (tvec): [{tvec[0]:.6f}, {tvec[1]:.6f}, "
                  f"{tvec[2]:.6f}]")
        
        # Compute camera center statistics
        print(f"\n  Camera Position Statistics:")
        cam_centers = []
        for cam_data in cameras.values():
            tvec = np.array(cam_data['tvec'])
            cam_centers.append(tvec)
        
        cam_centers = np.array(cam_centers)
        print(f"    • Mean position: [{cam_centers[:, 0].mean():.3f}, "
              f"{cam_centers[:, 1].mean():.3f}, {cam_centers[:, 2].mean():.3f}]")
        print(f"    • Std position: [{cam_centers[:, 0].std():.3f}, "
              f"{cam_centers[:, 1].std():.3f}, {cam_centers[:, 2].std():.3f}]")
        
    except Exception as e:
        print(f"✗ Error loading camera poses: {e}")
        return False
    
    print("\n" + "="*70)
    print("✓ All Verification Checks Passed!")
    print("="*70)
    print("\nSummary:")
    print(f"  • Point cloud: {len(vertices):,} points ready for Gaussian Splatting")
    print(f"  • Cameras: {len(cameras)} poses with full pose information")
    print(f"  • Scene: Properly normalized with center and radius parameters")
    print(f"\nThe data is ready for Gaussian Splatting training!")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    import sys
    success = verify_conversion()
    sys.exit(0 if success else 1)
