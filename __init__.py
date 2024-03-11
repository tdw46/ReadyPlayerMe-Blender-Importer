bl_info = {
    "name": "ReadyPlayerMe Blender Importer",
    "blender": (2, 80, 0),
    "category": "Import-Export",
    "description": "Import ReadyPlayerMe models into Blender",
    "author": "BeyondDev (Tyler Walker)",
    "version": (1, 0),
    "location": "File > Import > ReadyPlayerMe Import",
    "warning": "",  # Used for warning icon and text in addons panel
    "doc_url": "",  # Documentation URL (optional)
    "tracker_url": "",  # Tracker URL for reporting bugs (optional)
}

import bpy
import urllib.request
import os
from pathlib import Path

class ReadyPlayerMeImporter(bpy.types.Operator):
    """Import a ReadyPlayerMe model"""
    bl_idname = "import_scene.readyplayerme_importer"
    bl_label = "Import ReadyPlayerMe Model"
    bl_options = {'REGISTER', 'UNDO'}

    model_url: bpy.props.StringProperty(
        name="Model URL",
        description="URL of the ReadyPlayerMe model to import",
        default=""
    )

    quality_options = [
        ('high', "High", "High quality"),
        ('medium', "Medium", "Medium quality"),
        ('low', "Low", "Low quality"),
    ]

    quality: bpy.props.EnumProperty(
        name="Quality",
        description="Quality of the model",
        items=quality_options,
        default='low'
    )

    t_pose: bpy.props.BoolProperty(
        name="T Pose",
        description="Import model in T Pose",
        default=True
    )

    arkit_shapes: bpy.props.BoolProperty(
        name="ARKit Shapes",
        description="Include ARKit facial shapes",
        default=True
    )

    enable_texture_atlas: bpy.props.BoolProperty(
        name="Enable Texture Atlas",
        description="Whether to use a texture atlas",
        default=True
    )

    texture_atlas_size_options = [
        ('none', "None", "Do not use a texture atlas"),
        ('256', "256", "Texture atlas size 256"),
        ('512', "512", "Texture atlas size 512"),
        ('1024', "1024", "Texture atlas size 1024"),  # Default value
    ]

    texture_atlas_size: bpy.props.EnumProperty(
        name="Texture Atlas Size",
        description="Size of the texture atlas if enabled",
        items=texture_atlas_size_options,
        default='1024'
    )

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.download_and_import_model(context)
        return {'FINISHED'}
    
    def apply_pose_as_basis(context, aobj=None):
        if aobj is None:
            aobj = bpy.context.active_object

        if aobj.data.shape_keys:
            act_sk = aobj.active_shape_key
            ref_sk = aobj.data.shape_keys.reference_key

            act_defs = [(act_sk.data[d].co - dat.co) for d, dat in enumerate(ref_sk.data)]

            for sk in aobj.data.shape_keys.key_blocks:
                if sk not in (act_sk, ref_sk):
                    sk_defs = [(sk.data[d].co - dat.co) for d, dat in enumerate(ref_sk.data)]
                    for d, dat in enumerate(sk.data):
                        dat.co = ref_sk.data[d].co + act_defs[d] + sk_defs[d]

            while aobj.data.shape_keys.reference_key.name != act_sk.name:
                bpy.ops.object.shape_key_move(type='UP')

            for sk in aobj.data.shape_keys.key_blocks:
                if sk != act_sk:
                    sk.relative_key = act_sk

    def download_and_import_model(self, context):
        # First, try the original directory for storing downloaded models
        original_dir_path = os.path.join(os.path.dirname(bpy.path.abspath(bpy.data.filepath)), "gltf-DL")
        
        # Fallback directory in the user's Downloads directory
        downloads_path = str(Path.home() / "Downloads")
        fallback_dir_path = os.path.join(downloads_path, "gltf-DL")
        
        try:
            os.makedirs(original_dir_path, exist_ok=True)
            dir_path = original_dir_path
        except PermissionError:
            print("Permission denied for original directory, using fallback directory in Downloads.")
            os.makedirs(fallback_dir_path, exist_ok=True)
            dir_path = fallback_dir_path

        # Construct the URL based on user input
        model_url = self.model_url
        quality_parameter = f"?quality={self.quality}"
        pose_option = "&pose=T" if self.t_pose else ""
        arkit_option = "&morphTargets=mouthSmile,ARKit" if self.arkit_shapes else ""
        texture_atlas_option = f"&textureAtlas={self.texture_atlas_size}" if self.enable_texture_atlas and self.texture_atlas_size != 'none' else ""

        url = f"{model_url}{quality_parameter}{pose_option}{arkit_option}{texture_atlas_option}"
        
        # Download the file
        filename = os.path.join(dir_path, os.path.basename(url).split("?")[0])
        try:
            urllib.request.urlretrieve(url, filename)
            print(f"Downloaded {filename}")
        except Exception as e:
            print(f"Failed to download file: {e}")
            # Show that this happened in the bottom of blender window in the info
            self.report({'ERROR'}, f"Failed to download file: {e}  ||  (not all sizes + quality combinations are supported)")
            return {'CANCELLED'}
        
        # deselect all objects
        bpy.ops.object.select_all(action='DESELECT')

        # Import the downloaded model
        bpy.ops.import_scene.gltf(filepath=filename)

        # Update the viewport
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        bpy.context.view_layer.update()

        # Process the imported model
        # armature is the only armature in the selected objects
        armatures = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
        armature = armatures[0] if armatures else None
        armature.data.show_bone_custom_shapes = False


        child_meshes = [obj for obj in armature.children if obj.type == 'MESH']
        
        if len(child_meshes) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for mesh in child_meshes:
                mesh.select_set(True)
            bpy.context.view_layer.objects.active = child_meshes[0]
            bpy.ops.object.join()

        child_meshes = [obj for obj in armature.children if obj.type == 'MESH']

        if armatures and child_meshes:
            for mesh in child_meshes:
                bpy.context.view_layer.objects.active = mesh
                for modifier in mesh.modifiers:
                    if modifier.type == 'ARMATURE' and modifier.object == armature:
                        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=True, modifier=modifier.name)
                        break
                if mesh.data.shape_keys:
                    bpy.context.object.active_shape_key_index = len(mesh.data.shape_keys.key_blocks) - 1
                    self.apply_pose_as_basis( aobj= mesh)
                    mesh.data.shape_keys.key_blocks[1].name = "oldBasis"
                    mesh.data.shape_keys.key_blocks[0].name = "Basis"
            bpy.context.view_layer.objects.active = armature
            bpy.context.object.show_in_front = True
            bpy.ops.object.posemode_toggle()
            bpy.ops.pose.armature_apply(selected=False)

        return {'FINISHED'}
    

def menu_func_import(self, context):
    self.layout.operator(ReadyPlayerMeImporter.bl_idname, text="Ready Player Me Model (.glb URL)")


def register():
    bpy.utils.register_class(ReadyPlayerMeImporter)
    bpy.types.TOPBAR_MT_file_import.prepend(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ReadyPlayerMeImporter)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
