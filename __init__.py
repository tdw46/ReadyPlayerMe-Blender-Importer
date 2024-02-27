bl_info = {
    "name": "ReadyPlayerMe Blender Importer",
    "blender": (2, 80, 0),
    "category": "Object",
    "description": "Import ReadyPlayerMe models into Blender",
    "author": "BeyondDev (Tyler Walker)",
    "version": (1, 0),
    "location": "View3D > Tool Shelf > ReadyPlayerMe Import",
    "warning": "",  # Used for warning icon and text in addons panel
    "doc_url": "",  # Documentation URL (optional)
    "tracker_url": "",  # Tracker URL for reporting bugs (optional)
}

import bpy
import urllib.request
import os
import time

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

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.download_and_import_model(context)
        return {'FINISHED'}
    
    def apply_pose_as_basis(aobj=None):
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
        # Ensure the directory for storing downloaded models exists
        dir_path = os.path.join(os.path.dirname(bpy.path.abspath(bpy.data.filepath)), "gltf-DL")
        os.makedirs(dir_path, exist_ok=True)

        # Construct the URL based on user input
        model_url = self.model_url
        if self.t_pose:
            pose_option = "&pose=T"
        else:
            pose_option = ""
        if self.arkit_shapes:
            arkit_option = "&morphTargets=mouthSmile,ARKit"
        else:
            arkit_option = ""
        url = f"{model_url}?quality=high{arkit_option}{pose_option}"

        # Download the file
        filename = os.path.join(dir_path, os.path.basename(url).split("?")[0])
        try:
            urllib.request.urlretrieve(url, filename)
            print(f"Downloaded {filename}")
        except Exception as e:
            print(f"Failed to download file: {e}")
            return {'CANCELLED'}

        # Import the downloaded model
        bpy.ops.import_scene.gltf(filepath=filename)

        # Update the viewport
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        bpy.context.view_layer.update()

        # Process the imported model
        armatures = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
        meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if armatures and meshes:
            armature = armatures[0]
            for mesh in meshes:
                bpy.context.view_layer.objects.active = mesh
                for modifier in mesh.modifiers:
                    if modifier.type == 'ARMATURE' and modifier.object == armature:
                        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=True, modifier=modifier.name)
                        break
                if mesh.data.shape_keys:
                    bpy.context.object.active_shape_key_index = len(mesh.data.shape_keys.key_blocks) - 1
                    self.apply_pose_as_basis(mesh)
                    mesh.data.shape_keys.key_blocks[1].name = "oldBasis"
                    mesh.data.shape_keys.key_blocks[0].name = "Basis"
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.posemode_toggle()
            bpy.ops.pose.armature_apply(selected=False)

        return {'FINISHED'}

def register():
    bpy.utils.register_class(ReadyPlayerMeImporter)

def unregister():
    bpy.utils.unregister_class(ReadyPlayerMeImporter)

if __name__ == "__main__":
    register()
