"""Executed only by the pinned Blender binary with --factory-startup/--disable-autoexec."""

import json
import random
import sys
from pathlib import Path


def main():
    import bpy
    from mathutils import Vector

    args = sys.argv[sys.argv.index("--") + 1 :]
    config, output = json.loads(Path(args[0]).read_text()), Path(args[1])
    frames = []
    for scene_number in range(config["count"]):
        rng = random.Random(config["seed"] + scene_number)
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = config["render_samples"]
        scene.cycles.use_denoising = False
        scene.render.threads_mode = "FIXED"
        scene.render.threads = 2
        scene.render.resolution_x = scene.render.resolution_y = config["resolution"]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.film_transparent = False
        scene.render.fps = config["fps"]
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.3, 0.3, 1)
        if config["object_type"] == "cube":
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.65))
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=24, ring_count=12, radius=0.6, location=(0, 0, 0.65)
            )
        obj = bpy.context.object
        obj.pass_index = 1
        material = bpy.data.materials.new("Original procedural material")
        material.diffuse_color = (0.08 + rng.random() * 0.1, 0.2 + rng.random() * 0.4, 0.75, 1)
        obj.data.materials.append(material)
        bpy.ops.mesh.primitive_plane_add(size=20)
        floor = bpy.data.materials.new("Neutral floor")
        floor.diffuse_color = (0.65, 0.65, 0.65, 1)
        bpy.context.object.data.materials.append(floor)
        bpy.ops.object.light_add(type="AREA", location=(1, -2, 5))
        bpy.context.object.data.energy = 700
        bpy.context.object.data.shape = "DISK"
        bpy.context.object.data.size = 4
        bpy.ops.object.camera_add(location=(3, -4, 3))
        camera = bpy.context.object
        camera.rotation_euler = (Vector((0, 0, 0.6)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = 50
        camera.data.sensor_width = 36
        scene.camera = camera
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()
        layers = tree.nodes.new("CompositorNodeRLayers")
        bpy.context.view_layer.use_pass_object_index = True
        composite = tree.nodes.new("CompositorNodeComposite")
        tree.links.new(layers.outputs["Image"], composite.inputs["Image"])
        mask = tree.nodes.new("CompositorNodeIDMask")
        mask.index = 1
        mask.use_antialiasing = False
        tree.links.new(layers.outputs["IndexOB"], mask.inputs[0])
        output_node = tree.nodes.new("CompositorNodeOutputFile")
        output_node.base_path = str(output)
        output_node.format.file_format = "PNG"
        output_node.format.color_mode = "BW"
        output_node.format.color_depth = "8"
        tree.links.new(mask.outputs[0], output_node.inputs[0])
        for frame_index in range(config["frames_per_scene"]):
            scene.frame_set(frame_index + 1)
            obj.location.x = 0.15 * frame_index
            obj.rotation_euler.z = rng.random() * 0.3 + frame_index * 0.1
            identifier = f"scene_{scene_number:02d}_frame_{frame_index:02d}"
            rgb_file, scene_file = identifier + ".png", identifier + ".glb"
            output_node.file_slots[0].path = identifier + "_mask_"
            scene.render.filepath = str(output / rgb_file)
            bpy.ops.render.render(write_still=True)
            bpy.ops.export_scene.gltf(
                filepath=str(output / scene_file),
                export_format="GLB",
                export_cameras=True,
                export_lights=True,
            )
            focal = config["resolution"] * camera.data.lens / camera.data.sensor_width
            frames.append(
                {
                    "joint_sample_id": identifier,
                    "episode_id": f"scene_{scene_number:02d}",
                    "frame_index": frame_index,
                    "timestamp_seconds": frame_index / config["fps"],
                    "rgb_file": rgb_file,
                    "scene_file": scene_file,
                    "mask_file": identifier + f"_mask_{frame_index + 1:04d}.png",
                    "camera_intrinsics": [
                        [focal, 0, config["resolution"] / 2],
                        [0, focal, config["resolution"] / 2],
                        [0, 0, 1],
                    ],
                    "camera_to_world": [list(row) for row in camera.matrix_world],
                    "object_to_world": [list(row) for row in obj.matrix_world],
                    "axes": "Blender right-handed Z-up; camera local -Z forward, +Y up",
                    "length_unit": "meter",
                    "angle_unit": "radian",
                    "object_type": config["object_type"],
                    "seed": config["seed"] + scene_number,
                }
            )
    (output / "frames.json").write_text(json.dumps(frames))


if __name__ == "__main__":
    main()
