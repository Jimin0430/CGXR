#!/usr/bin/env python3
"""
Convert COLMAP SfM data to Gaussian Splatting format
"""
import os
import sys
import json
import numpy as np
from pathlib import Path
from plyfile import PlyData, PlyElement

# Import the correct COLMAP binary readers
from colmap_loader import (
    read_intrinsics_binary, read_extrinsics_binary, 
    read_points3D_binary, qvec2rotmat
)

def storePly(path, xyz, rgb):
    """Store point cloud as PLY file"""
    dtype = [('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')]
    
    normals = np.zeros_like(xyz)
    elements = np.empty(xyz.shape[0], dtype=dtype)
    attributes = np.concatenate((xyz, normals, rgb), axis=1)
    elements[:] = list(map(tuple, attributes))
    
    vertex_element = PlyElement.describe(elements, 'vertex')
    ply_data = PlyData([vertex_element])
    ply_data.write(path)
    print(f"    PLY file saved: {path}")

def fetchPly(path):
    """Load point cloud from PLY file"""
    plydata = PlyData.read(path)
    vertices = plydata['vertex']
    positions = np.vstack([vertices['x'], vertices['y'], vertices['z']]).T
    colors = np.vstack([vertices['red'], vertices['green'], vertices['blue']]).T / 255.0
    normals = np.vstack([vertices['nx'], vertices['ny'], vertices['nz']]).T
    return {"positions": positions, "colors": colors, "normals": normals}

def convert_sfm_to_gaussian(sfm_path):
    """
    Convert SfM COLMAP data to Gaussian Splatting format
    """
    
    if not os.path.exists(sfm_path):
        print(f"Error: Path does not exist: {sfm_path}")
        return False
    
    sparse_0_path = os.path.join(sfm_path, "sparse", "0")
    if not os.path.exists(sparse_0_path):
        print(f"Error: COLMAP sparse/0 directory not found at: {sparse_0_path}")
        return False
    
    # Check if COLMAP files exist
    cameras_bin = os.path.join(sparse_0_path, "cameras.bin")
    images_bin = os.path.join(sparse_0_path, "images.bin")
    points3d_bin = os.path.join(sparse_0_path, "points3D.bin")
    
    if not os.path.exists(cameras_bin) or not os.path.exists(images_bin):
        print(f"Error: COLMAP camera files not found in {sparse_0_path}")
        return False
    
    if not os.path.exists(points3d_bin):
        print(f"Error: COLMAP points3D file not found in {sparse_0_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"Converting SfM data from: {sfm_path}")
    print(f"{'='*60}\n")
    
    try:
        # Read COLMAP camera intrinsics
        print("Step 1: Reading COLMAP camera data...")
        cameras = read_intrinsics_binary(cameras_bin)
        images = read_extrinsics_binary(images_bin)
        
        print(f"  ✓ Loaded {len(cameras)} camera model(s)")
        print(f"  ✓ Loaded {len(images)} image pose(s)")
        
        # Convert points3D.bin to PLY if needed
        print("\nStep 2: Converting point cloud to PLY format...")
        ply_path = os.path.join(sparse_0_path, "points3D.ply")
        
        if not os.path.exists(ply_path):
            print(f"  Reading points3D.bin...")
            xyz, rgb, errors = read_points3D_binary(points3d_bin)
            rgb = rgb.astype(np.uint8)
            
            print(f"  Saving PLY file with {len(xyz)} points...")
            storePly(ply_path, xyz, rgb)
        else:
            print(f"  PLY file already exists: {ply_path}")
        
        # Verify point cloud
        print("\nStep 3: Verifying point cloud...")
        pcd = fetchPly(ply_path)
        pos = pcd['positions']
        col = pcd['colors']
        print(f"  ✓ Point cloud loaded: {len(pos)} points")
        print(f"  ✓ Color range: [{col.min():.3f}, {col.max():.3f}]")
        print(f"  ✓ Position range:")
        print(f"      X: [{pos[:, 0].min():.3f}, {pos[:, 0].max():.3f}]")
        print(f"      Y: [{pos[:, 1].min():.3f}, {pos[:, 1].max():.3f}]")
        print(f"      Z: [{pos[:, 2].min():.3f}, {pos[:, 2].max():.3f}]")
        
        # Calculate camera normalization (NeRF++ style)
        print("\nStep 4: Computing camera normalization...")
        cam_centers = []
        for image_id in images:
            image = images[image_id]
            qvec = image.qvec
            tvec = image.tvec
            # Convert qvec to rotation matrix
            # In COLMAP: world-to-camera = [R | t] where R = qvec2rotmat(qvec)
            # So camera center in world coords is: -R^T @ t = -R.transpose() @ t
            R = qvec2rotmat(qvec)
            # R is rotation matrix from world to camera  
            # Camera center: C = -R^{-1} @ t = -R^T @ t (since R is orthogonal)
            cam_center = -R.T @ tvec
            cam_centers.append(cam_center)
        
        cam_centers = np.array(cam_centers).T  # Shape: (3, num_cameras)
        avg_cam_center = np.mean(cam_centers, axis=1, keepdims=True)
        center = avg_cam_center
        dist = np.linalg.norm(cam_centers - center, axis=0, keepdims=True)
        diagonal = np.max(dist)
        radius = diagonal * 1.1
        translate = -center.flatten()
        
        print(f"  ✓ Scene center: {center.flatten()}")
        print(f"  ✓ Scene radius: {radius:.3f}")
        
        # Save metadata
        print("\nStep 5: Saving metadata...")
        metadata = {
            "num_cameras": len(images),
            "num_camera_models": len(cameras),
            "num_points": len(pos),
            "camera_normalization": {
                "translate": translate.tolist(),
                "radius": float(radius)
            },
            "output_ply": ply_path,
            "cameras": {str(cid): {
                "model": str(cameras[cid].model),
                "width": int(cameras[cid].width),
                "height": int(cameras[cid].height),
                "params": cameras[cid].params.tolist()
            } for cid in cameras}
        }
        
        metadata_path = os.path.join(sparse_0_path, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ Metadata saved: {metadata_path}")
        
        # Save camera poses
        print("\nStep 6: Saving camera poses...")
        camera_info = {}
        for image_id in images:
            img = images[image_id]
            camera_info[img.name] = {
                "image_id": int(image_id),
                "camera_id": int(img.camera_id),
                "qvec": img.qvec.tolist(),
                "tvec": img.tvec.tolist()
            }
        
        cameras_path = os.path.join(sparse_0_path, "cameras_poses.json")
        with open(cameras_path, 'w') as f:
            json.dump(camera_info, f, indent=2)
        print(f"  ✓ Camera poses saved: {cameras_path}")
        
        print(f"\n{'='*60}")
        print(f"✓ Conversion completed successfully!")
        print(f"{'='*60}")
        print(f"\nOutput files created:")
        print(f"  1. {ply_path}")
        print(f"     → Point cloud with {len(pos)} 3D points for Gaussian Splatting")
        print(f"  2. {metadata_path}")
        print(f"     → Scene metadata (normalization, cameras info)")
        print(f"  3. {cameras_path}")
        print(f"     → Camera poses ({len(images)} cameras)")
        print(f"\n✓ To check the results:")
        print(f"  • View the PLY file using CloudCompare or Meshlab")
        print(f"    https://www.cloudcompare.org/ or https://www.meshlab.net/")
        print(f"  • Or use Python to inspect:")
        print(f"    from plyfile import PlyData")
        print(f"    ply = PlyData.read('{ply_path}')")
        print(f"    print(f'Points: {{len(ply[\"vertex\"])}}')") 
        print(f"\n✓ Next steps for Gaussian Splatting training:")
        print(f"  • Use the points3D.ply as initial point cloud")
        print(f"  • Feed camera poses from cameras_poses.json to the training pipeline")
        print(f"  • The point cloud will be optimized during training")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sfm_path = r"d:\JM\cgxr\CGXR\Extract_SfM"
    success = convert_sfm_to_gaussian(sfm_path)
    sys.exit(0 if success else 1)
