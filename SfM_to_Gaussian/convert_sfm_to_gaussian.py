#!/usr/bin/env python3
"""
Convert COLMAP SfM data to Gaussian Splatting format
"""
import os
import sys
import json
from pathlib import Path

# Add the current directory to Python path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset_readers import readColmapSceneInfo, storePly, fetchPly
from colmap_loader import read_points3D_binary, read_points3D_text

def convert_sfm_to_gaussian(sfm_path, output_path=None):
    """
    Convert SfM COLMAP data to Gaussian Splatting format
    
    Args:
        sfm_path: Path to directory containing sparse/0 COLMAP data
        output_path: Optional output path for the converted data (default: same as sfm_path)
    """
    
    if not os.path.exists(sfm_path):
        print(f"Error: Path does not exist: {sfm_path}")
        return False
    
    sparse_0_path = os.path.join(sfm_path, "sparse", "0")
    if not os.path.exists(sparse_0_path):
        print(f"Error: COLMAP sparse/0 directory not found at: {sparse_0_path}")
        return False
    
    # Check if COLMAP files exist
    bin_path = os.path.join(sparse_0_path, "points3D.bin")
    txt_path = os.path.join(sparse_0_path, "points3D.txt")
    
    if not os.path.exists(bin_path) and not os.path.exists(txt_path):
        print(f"Error: COLMAP points3D files not found in {sparse_0_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"Converting SfM data from: {sfm_path}")
    print(f"{'='*60}\n")
    
    try:
        # Read COLMAP data
        print("Step 1: Reading COLMAP camera data...")
        scene_info = readColmapSceneInfo(
            path=sfm_path,
            images=None,  # images folder optional
            depths="",    # no depth data
            eval=False,   # training mode
            train_test_exp=False
        )
        
        print(f"  ✓ Loaded {len(scene_info.train_cameras)} training cameras")
        print(f"  ✓ Loaded {len(scene_info.test_cameras)} test cameras")
        
        # Convert points3D.bin to PLY if needed
        print("\nStep 2: Converting point cloud to PLY format...")
        ply_path = os.path.join(sparse_0_path, "points3D.ply")
        
        if not os.path.exists(ply_path):
            try:
                print(f"  Reading points3D.bin...")
                xyz, rgb, _ = read_points3D_binary(bin_path)
            except:
                print(f"  Reading points3D.txt (binary not available)...")
                xyz, rgb, _ = read_points3D_text(txt_path)
            
            print(f"  Saving PLY file with {len(xyz)} points...")
            storePly(ply_path, xyz, rgb)
        else:
            print(f"  PLY file already exists")
        
        # Verify point cloud
        print("\nStep 3: Verifying point cloud...")
        pcd = fetchPly(ply_path)
        if pcd is not None:
            print(f"  ✓ Point cloud loaded: {len(pcd.points)} points")
            print(f"  ✓ Color range: R[{pcd.colors.min():.3f}, {pcd.colors.max():.3f}]")
            print(f"  ✓ Position range:")
            print(f"      X: [{pcd.points[:, 0].min():.3f}, {pcd.points[:, 0].max():.3f}]")
            print(f"      Y: [{pcd.points[:, 1].min():.3f}, {pcd.points[:, 1].max():.3f}]")
            print(f"      Z: [{pcd.points[:, 2].min():.3f}, {pcd.points[:, 2].max():.3f}]")
        
        # Save metadata
        print("\nStep 4: Saving metadata...")
        metadata = {
            "num_train_cameras": len(scene_info.train_cameras),
            "num_test_cameras": len(scene_info.test_cameras),
            "num_points": len(pcd.points) if pcd else 0,
            "nerf_normalization": {
                "translate": scene_info.nerf_normalization["translate"].tolist(),
                "radius": float(scene_info.nerf_normalization["radius"])
            },
            "output_ply": ply_path,
            "camera_normalization": scene_info.nerf_normalization
        }
        
        metadata_path = os.path.join(sparse_0_path, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ Metadata saved to: {metadata_path}")
        
        print(f"\n{'='*60}")
        print(f"✓ Conversion completed successfully!")
        print(f"{'='*60}")
        print(f"\nOutput files:")
        print(f"  • Point cloud: {ply_path}")
        print(f"  • Metadata: {metadata_path}")
        print(f"\nNext steps:")
        print(f"  1. Use {ply_path} as input for Gaussian Splatting training")
        print(f"  2. The point cloud is the initial SfM points")
        print(f"  3. Camera parameters are stored in the metadata")
        
        return True
        
    except Exception as e:
        print(f"\nError during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Source SfM data path
    sfm_path = r"d:\JM\cgxr\CGXR\Extract_SfM"
    
    success = convert_sfm_to_gaussian(sfm_path)
    sys.exit(0 if success else 1)
