bl_info = {
    "name": "ReadyPlayerMe Blender Importer",
    "blender": (2, 80, 0),
    "category": "Import-Export",
    "description": "Import ReadyPlayerMe models into Blender",
    "author": "BeyondDev (Tyler Walker)",
    "version": (2, 2, 2),
    "location": "File > Import > ReadyPlayerMe Import",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
import urllib.request
import os
from pathlib import Path
import sys
import threading
import json
import urllib.parse
import subprocess
import tempfile
import shutil
from bpy.utils import previews
import time

def _find_system_python_command():
    candidates = []
    if sys.platform.startswith('win'):
        candidates.extend(['py', 'python', 'python3'])
    else:
        candidates.extend(['python3', 'python'])
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None

def _is_pywebview_available():
    cmd = _find_system_python_command()
    if not cmd:
        return False
    try:
        res = subprocess.run([cmd, '-c', 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("webview") else 1)'], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    try:
        res2 = subprocess.run([cmd, '-m', 'pip', 'show', 'pywebview'], capture_output=True, text=True, timeout=5)
        return res2.returncode == 0
    except Exception:
        return False

def _prefs_file_path():
    return os.path.join(os.path.dirname(__file__), 'rpm_prefs.json')


def _load_prefs_from_disk():
    try:
        path = _prefs_file_path()
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        p = bpy.context.preferences.addons[__name__].preferences
        em = (data.get('email') or '').strip()
        pw = data.get('password') or ''
        if em:
            p.login_email = em
        if pw:
            p.login_password = pw
        
        # Load avatar items
        avatar_list = data.get('avatar_items') or []
        p.avatar_items.clear()
        for item_data in avatar_list:
            new_item = p.avatar_items.add()
            new_item.glb_url = item_data.get('glb_url') or ''
            new_item.thumb_url = item_data.get('thumb_url') or ''
            new_item.avatar_id = item_data.get('avatar_id') or ''
        
        # Load dev mode
        if 'dev_mode' in data:
            p.dev_mode = data.get('dev_mode', False)
        
        print(f'RPM: Loaded {len(avatar_list)} avatars from disk')
    except Exception as e:
        print('RPM: failed to load prefs from disk', e)

def _install_pywebview():
    cmd = _find_system_python_command()
    if not cmd:
        return False, "No system Python found. Install Python first."
    try:
        res = subprocess.run([cmd, '-m', 'pip', 'install', '--user', 'pywebview'], capture_output=True, text=True)
        ok = res.returncode == 0
        msg = res.stdout if ok else (res.stderr or res.stdout)
        return ok, msg
    except Exception as e:
        return False, str(e)

PYWEBVIEW_OK = False
preview_col = None

class RPM_OT_OpenUIWebview(bpy.types.Operator):
    """Open Ready Player Me UI in webview"""
    bl_idname = "rpm.webviewui"
    bl_label = "RPM WebviewUI"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    _timer = None
    _webview_process = None
    _ui_window = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            # Check if webview is still running
            if self._webview_process and self._webview_process.poll() is not None:
                self.cancel(context)
                return {'CANCELLED'}
            
            # Check for download requests
            addon_dir = os.path.dirname(__file__)
            req_file = os.path.join(addon_dir, 'rpm_download_request.json')
            if os.path.exists(req_file):
                try:
                    with open(req_file, 'r', encoding='utf-8') as f:
                        options = json.load(f)
                    os.remove(req_file)
                    
                    # Trigger import
                    url = options.get('url', '')
                    if url:
                        bpy.ops.rpm.native_import(
                            'EXEC_DEFAULT',
                            model_url=url,
                            quality=options.get('quality', 'low'),
                            t_pose=options.get('t_pose', True),
                            arkit_shapes=options.get('arkit_shapes', True),
                            enable_texture_atlas=options.get('texture_atlas', True),
                            texture_atlas_size=options.get('texture_atlas_size', '1024')
                        )
                        print(f"RPM: Imported {options.get('avatar_id', 'avatar')}")
                except Exception as e:
                    print(f"RPM: Error processing download request: {e}")
        
        if event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        # Check pywebview
        if not _is_pywebview_available():
            self.report({'ERROR'}, "pywebview not available. Install in addon preferences.")
            return {'CANCELLED'}
        
        try:
            # Get HTML path
            addon_dir = os.path.dirname(__file__)
            html_path = os.path.join(addon_dir, 'rpm_ui.html')
            
            if not os.path.exists(html_path):
                self.report({'ERROR'}, f"UI file not found: {html_path}")
                return {'CANCELLED'}
            
            # Write default property values for webview
            defaults_file = os.path.join(addon_dir, 'rpm_ui_defaults.json')
            try:
                defaults = {
                    'quality': 'high',
                    't_pose': True,
                    'arkit_shapes': True,
                    'enable_texture_atlas': True,
                    'texture_atlas_size': '1024'
                }
                with open(defaults_file, 'w', encoding='utf-8') as f:
                    json.dump(defaults, f)
            except Exception as e:
                print(f"RPM: Could not write defaults: {e}")
            
            # Save dev_mode to prefs file for webview helper
            prefs_file = os.path.join(addon_dir, 'rpm_prefs.json')
            try:
                prefs_data = {}
                if os.path.exists(prefs_file):
                    with open(prefs_file, 'r', encoding='utf-8') as f:
                        prefs_data = json.load(f)
                
                prefs = context.preferences.addons[__name__].preferences
                prefs_data['dev_mode'] = prefs.dev_mode
                prefs_data['email'] = prefs.login_email or ''
                prefs_data['password'] = prefs.login_password or ''
                
                with open(prefs_file, 'w', encoding='utf-8') as f:
                    json.dump(prefs_data, f)
            except Exception as e:
                print(f"RPM: Could not save dev_mode: {e}")
            
            # Start webview in subprocess
            helper_path = os.path.join(addon_dir, 'rpm_ui_webview.py')
            cmd = _find_system_python_command()
            
            if not cmd:
                self.report({'ERROR'}, "No Python command found")
                return {'CANCELLED'}
            
            # Set env vars
            env = os.environ.copy()
            env['RPM_HTML_PATH'] = html_path
            env['RPM_ADDON_NAME'] = __name__
            # Unbuffer Python IO for real-time logging from child
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            self._webview_process = subprocess.Popen(
                [cmd, helper_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )

            # Stream child stdout/stderr to Blender console
            def _forward_stream(stream, prefix):
                try:
                    for line in iter(stream.readline, ''):
                        try:
                            print(f"{prefix}{line.rstrip()}")
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                t_out = threading.Thread(target=_forward_stream, args=(self._webview_process.stdout, 'RPM UI> '), daemon=True)
                t_err = threading.Thread(target=_forward_stream, args=(self._webview_process.stderr, 'RPM UI ERR> '), daemon=True)
                t_out.start()
                t_err.start()
            except Exception:
                pass
            
            # Start modal timer
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            
            print("RPM: UI webview started")
            return {'RUNNING_MODAL'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start UI webview: {e}")
            return {'CANCELLED'}
    
    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        if self._webview_process:
            try:
                self._webview_process.terminate()
            except:
                pass
        print("RPM: UI webview closed")

class ReadyPlayerMeImporter(bpy.types.Operator):
    """RPM Native Import"""
    bl_idname = "rpm.native_import"
    bl_label = "RPM Native Import"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    model_url: bpy.props.StringProperty(
        name="Model URL",
        description="URL of the ReadyPlayerMe model to import",
        default=""
    )

    # Removed mode property - now using single unified tab

    quality_options = [
        ('high', "High", "High quality"),
        ('medium', "Medium", "Medium quality"),
        ('low', "Low", "Low quality"),
    ]

    quality: bpy.props.EnumProperty(
        name="Quality",
        description="Quality of the model",
        items=quality_options,
        default='high'
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
        ('1024', "1024", "Texture atlas size 1024"),
    ]

    texture_atlas_size: bpy.props.EnumProperty(
        name="Texture Atlas Size",
        description="Size of the texture atlas if enabled",
        items=texture_atlas_size_options,
        default='1024'
    )

    def execute(self, context):
        # Only execute if model_url is provided
        if self.model_url:
            return self.download_and_import_model(context)
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
        original_dir_path = os.path.join(os.path.dirname(bpy.path.abspath(bpy.data.filepath)), "gltf-DL")
        
        downloads_path = str(Path.home() / "Downloads")
        fallback_dir_path = os.path.join(downloads_path, "gltf-DL")
        
        try:
            os.makedirs(original_dir_path, exist_ok=True)
            dir_path = original_dir_path
        except PermissionError:
            print("Permission denied for original directory, using fallback directory in Downloads.")
            os.makedirs(fallback_dir_path, exist_ok=True)
            dir_path = fallback_dir_path

        model_url = self.model_url
        parsed = urllib.parse.urlparse(model_url)
        qs = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        qs['quality'] = self.quality
        if self.t_pose:
            qs['pose'] = 'T'
        else:
            qs.pop('pose', None)
        if self.arkit_shapes:
            qs['morphTargets'] = 'mouthSmile,ARKit'
        else:
            qs.pop('morphTargets', None)
        if self.enable_texture_atlas and self.texture_atlas_size != 'none':
            qs['textureAtlas'] = self.texture_atlas_size
        else:
            qs.pop('textureAtlas', None)
        new_query = urllib.parse.urlencode(qs, doseq=True)
        url = urllib.parse.urlunparse(parsed._replace(query=new_query))
        
        filename = os.path.join(dir_path, os.path.basename(url).split("?")[0])
        try:
            urllib.request.urlretrieve(url, filename)
            print(f"Downloaded {filename}")
        except Exception as e:
            print(f"Failed to download file: {e}")
            self.report({'ERROR'}, f"Failed to download file: {e}  ||  (not all sizes + quality combinations are supported)")
            return {'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.import_scene.gltf(filepath=filename)

        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        bpy.context.view_layer.update()

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
                    self.apply_pose_as_basis(aobj=mesh)
                    mesh.data.shape_keys.key_blocks[1].name = "oldBasis"
                    mesh.data.shape_keys.key_blocks[0].name = "Basis"
            bpy.context.view_layer.objects.active = armature
            bpy.context.object.show_in_front = True
            bpy.ops.object.posemode_toggle()
            bpy.ops.pose.armature_apply(selected=False)

        return {'FINISHED'}
    

def menu_func_import(self, context):
    print(f"RPM: menu_func_import called. PYWEBVIEW_OK={PYWEBVIEW_OK}")
    self.layout.operator(RPM_OT_OpenUIWebview.bl_idname, text="Ready Player Me")


def register():
    global PYWEBVIEW_OK
    bpy.utils.register_class(RPM_AvatarItem)
    bpy.utils.register_class(RPM_OT_OpenUIWebview)
    bpy.utils.register_class(ReadyPlayerMeImporter)
    bpy.utils.register_class(ReadyPlayerMePreferences)
    bpy.utils.register_class(RPM_OT_InstallDependenciesModal)
    PYWEBVIEW_OK = _is_pywebview_available()
    bpy.types.WindowManager.rpm_dep_install_running = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.rpm_dep_install_msg = bpy.props.StringProperty(default="")
    bpy.types.TOPBAR_MT_file_import.prepend(menu_func_import)
    global preview_col
    preview_col = previews.new()
    try:
        _load_prefs_from_disk()
    except Exception:
        pass

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(RPM_OT_InstallDependenciesModal)
    bpy.utils.unregister_class(ReadyPlayerMePreferences)
    bpy.utils.unregister_class(ReadyPlayerMeImporter)
    bpy.utils.unregister_class(RPM_OT_OpenUIWebview)
    bpy.utils.unregister_class(RPM_AvatarItem)
    try:
        del bpy.types.WindowManager.rpm_dep_install_running
        del bpy.types.WindowManager.rpm_dep_install_msg
    except Exception:
        pass
    global preview_col
    try:
        if preview_col:
            previews.remove(preview_col)
            preview_col = None
    except Exception:
        pass

rpm_event_queue = []

class RPM_AvatarItem(bpy.types.PropertyGroup):
    glb_url: bpy.props.StringProperty(name="GLB URL", default="")
    thumb_url: bpy.props.StringProperty(name="Thumbnail URL", default="")
    avatar_id: bpy.props.StringProperty(name="Avatar ID", default="")

def _get_preview_icon(thumb_url, key):
    global preview_col
    try:
        if not preview_col:
            return 0
        k = f"rpm_{key}"
        if k in preview_col:
            return preview_col[k].icon_id
        clean = thumb_url.split('?')[0]
        fd, tmp = tempfile.mkstemp(prefix='rpm_thumb_', suffix=os.path.splitext(clean)[1] or '.png')
        os.close(fd)
        urllib.request.urlretrieve(thumb_url, tmp)
        preview_col.load(k, tmp, 'IMAGE')
        return preview_col[k].icon_id
    except Exception as e:
        print('RPM: preview load error', e)
        return 0


class ReadyPlayerMePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    scraped_avatars_json: bpy.props.StringProperty(
        name="Scraped Avatars JSON",
        default=""
    )
    
    avatar_items: bpy.props.CollectionProperty(
        type=RPM_AvatarItem,
        name="Avatar Items"
    )
    login_email: bpy.props.StringProperty(
        name="Login Email",
        default=""
    )
    login_password: bpy.props.StringProperty(
        name="Login Password",
        default="",
        subtype='PASSWORD'
    )
    dev_mode: bpy.props.BoolProperty(
        name="Developer Mode",
        description="Show developer webview window during avatar refresh",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        installed = _is_pywebview_available()
        deps = layout.box()
        r = deps.row(align=True)
        r.label(text="pywebview", icon=('CHECKMARK' if installed else 'CANCEL'))

        box = layout.box()
        box.prop(self, 'login_email')
        box.prop(self, 'login_password')
        
        dev_box = layout.box()
        dev_box.prop(self, 'dev_mode')
        if self.dev_mode:
            dev_box.label(text="Developer webview will be visible", icon='INFO')

        if not installed:
            ibox = layout.box()
            if wm.rpm_dep_install_running:
                ibox.label(text="Installing pywebview... This may take a minute.")
                if wm.rpm_dep_install_msg:
                    ibox.label(text=wm.rpm_dep_install_msg[:200])
            else:
                row = ibox.row()
                row.enabled = not wm.rpm_dep_install_running
                row.operator(RPM_OT_InstallDependenciesModal.bl_idname, text="Install Required Packages")
                if wm.rpm_dep_install_msg:
                    ibox.label(text=wm.rpm_dep_install_msg[:200])

class RPM_OT_InstallDependenciesModal(bpy.types.Operator):
    bl_idname = "readyplayerme.install_dependencies_modal"
    bl_label = "Install Required Packages"
    bl_options = {'INTERNAL'}

    _thread = None
    _timer = None
    _ok = None
    _msg = ""

    def invoke(self, context, event):
        wm = context.window_manager
        installed = _is_pywebview_available()
        if installed:
            self.report({'INFO'}, "pywebview already installed.")
            return {'CANCELLED'}
        cmd = _find_system_python_command()
        if not cmd:
            wm.rpm_dep_install_msg = "No system Python found. Install Python first."
            self.report({'ERROR'}, wm.rpm_dep_install_msg)
            return {'CANCELLED'}
        wm.rpm_dep_install_running = True
        wm.rpm_dep_install_msg = "Starting install..."

        def worker():
            ok, msg = _install_pywebview()
            self._ok = ok
            self._msg = msg

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        self._timer = wm.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager
        if event.type == 'TIMER':
            if self._thread and self._thread.is_alive():
                txt = wm.rpm_dep_install_msg or "Installing pywebview"
                if txt.endswith("..."):
                    wm.rpm_dep_install_msg = "Installing pywebview."
                elif txt.endswith(".."):
                    wm.rpm_dep_install_msg = "Installing pywebview..."
                else:
                    wm.rpm_dep_install_msg = "Installing pywebview.."
                return {'RUNNING_MODAL'}
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            wm.rpm_dep_install_running = False
            if self._ok:
                wm.rpm_dep_install_msg = "pywebview installed."
                global PYWEBVIEW_OK
                PYWEBVIEW_OK = _is_pywebview_available()
                self.report({'INFO'}, "pywebview installed.")
                return {'FINISHED'}
            else:
                wm.rpm_dep_install_msg = f"Install failed: {str(self._msg)[:200]}"
                self.report({'ERROR'}, wm.rpm_dep_install_msg)
                return {'CANCELLED'}
        return {'PASS_THROUGH'}



if __name__ == "__main__":
    register()