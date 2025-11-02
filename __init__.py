bl_info = {
    "name": "ReadyPlayerMe Blender Importer",
    "blender": (2, 80, 0),
    "category": "Import-Export",
    "description": "Import ReadyPlayerMe models into Blender",
    "author": "BeyondDev (Tyler Walker)",
    "version": (1, 0, 64),
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

SUBDOMAIN = 'beyond-rpm-downloader'
CREATOR_URL = f'https://{SUBDOMAIN}.readyplayer.me/avatar'

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

def _save_prefs_to_disk(prefs):
    try:
        path = _prefs_file_path()
        # Save avatar items as well
        avatar_list = []
        for item in prefs.avatar_items:
            avatar_list.append({
                'glb_url': item.glb_url,
                'thumb_url': item.thumb_url,
                'avatar_id': item.avatar_id
            })
        
        data = {
            'email': prefs.login_email or '',
            'password': prefs.login_password or '',
            'avatar_items': avatar_list
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print('RPM: failed to save prefs to disk', e)

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

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context):
        # Only execute if model_url is provided (from URL import)
        if self.model_url:
            return self.download_and_import_model(context)
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        
        # Top section: Refresh button and URL input
        _installed = _is_pywebview_available()
        if _installed:
            layout.operator(RPM_OT_OpenMyAvatars.bl_idname, text="Refresh My Avatars List", icon='FILE_REFRESH')
        else:
            box = layout.box()
            box.label(text="pywebview not installed. Install in Add-on Preferences.", icon='ERROR')
        
        layout.separator()
        layout.prop(self, 'model_url', text="Or Import from URL")
        
        layout.separator()
        
        # Import options section
        opt = layout.box()
        opt.label(text="Import Options", icon='PREFERENCES')
        opt.prop(self, 'quality')
        opt.prop(self, 't_pose')
        opt.prop(self, 'arkit_shapes')
        opt.prop(self, 'enable_texture_atlas')
        if self.enable_texture_atlas:
            opt.prop(self, 'texture_atlas_size')
        
        layout.separator()
        
        # Avatar grid from persistent collection
        try:
            prefs = bpy.context.preferences.addons[__name__].preferences
            items = list(prefs.avatar_items)
        except Exception:
            items = []
        
        if items:
            layout.label(text="My Avatars:", icon='COMMUNITY')
            # Use row with splits to ensure consistent column widths
            for i in range(0, len(items), 3):
                row = layout.row(align=True)
                # Create 3 equal columns using split
                col1 = row.column(align=True)
                col2 = row.column(align=True)
                col3 = row.column(align=True)
                
                columns = [col1, col2, col3]
                
                for j in range(3):
                    if i + j < len(items):
                        it = items[i + j]
                        glb = it.glb_url
                        thumb = it.thumb_url
                        aid = it.avatar_id
                        
                        # Create a box for each avatar
                        box = columns[j].box()
                        col = box.column(align=True)
                        
                        # Try to display thumbnail using template_icon
                        if thumb:
                            img = _get_or_load_image(thumb, aid)
                            if img and hasattr(img, 'preview') and img.preview:
                                try:
                                    col.template_icon(icon_value=img.preview.icon_id, scale=6.0)
                                except Exception as e:
                                    print(f'RPM: template_icon error: {e}')
                                    col.label(text="", icon='ARMATURE_DATA')
                            else:
                                col.label(text="", icon='ARMATURE_DATA')
                        else:
                            col.label(text="", icon='ARMATURE_DATA')
                        
                        # Add download button below thumbnail with icon and tooltip
                        op = col.operator(RPM_OT_ImportAvatarURL.bl_idname, text="Download", icon='IMPORT')
                        op.url = glb
                        op.avatar_id_display = aid  # For tooltip
                        op.quality = self.quality
                        op.t_pose = self.t_pose
                        op.arkit_shapes = self.arkit_shapes
                        op.enable_texture_atlas = self.enable_texture_atlas
                        op.texture_atlas_size = self.texture_atlas_size
    
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
    self.layout.operator(ReadyPlayerMeImporter.bl_idname, text="Ready Player Me (My Avatars / URL)")


def register():
    global PYWEBVIEW_OK
    bpy.utils.register_class(RPM_AvatarItem)
    bpy.utils.register_class(ReadyPlayerMeImporter)
    bpy.utils.register_class(ReadyPlayerMePreferences)
    bpy.utils.register_class(RPM_OT_InstallDependenciesModal)
    bpy.utils.register_class(RPM_OT_OpenMyAvatars)
    bpy.utils.register_class(RPM_OT_ImportAvatarURL)
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
    bpy.utils.unregister_class(RPM_OT_OpenMyAvatars)
    bpy.utils.unregister_class(RPM_OT_InstallDependenciesModal)
    bpy.utils.unregister_class(RPM_OT_ImportAvatarURL)
    bpy.utils.unregister_class(ReadyPlayerMePreferences)
    bpy.utils.unregister_class(ReadyPlayerMeImporter)
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

def _get_or_load_image(thumb_url, key):
    """Load thumbnail into bpy.data.images and return the image object"""
    try:
        # Use a safe filename/identifier
        safe_key = key.replace('-', '_')[:20]
        img_identifier = f"rpm_thumb_{safe_key}"
        
        # First check if already loaded in Blender (packed or not)
        for img in bpy.data.images:
            # Check by name pattern or filepath containing our identifier
            if img_identifier in img.name or (img.filepath and safe_key in img.filepath):
                # Found it! Just ensure preview exists
                if not img.preview:
                    img.preview_ensure()
                return img
        
        # Not loaded yet - need to download, load, pack, and delete
        addon_dir = os.path.dirname(__file__)
        thumbs_dir = os.path.join(addon_dir, 'thumbnail_cache')
        os.makedirs(thumbs_dir, exist_ok=True)
        
        clean = thumb_url.split('?')[0]
        ext = os.path.splitext(clean)[1] or '.png'
        thumb_filename = f"rpm_{safe_key}{ext}"
        thumb_path = os.path.join(thumbs_dir, thumb_filename)
        
        # Download if not cached
        if not os.path.exists(thumb_path):
            urllib.request.urlretrieve(thumb_url, thumb_path)
        
        # Load into Blender
        img = bpy.data.images.load(thumb_path, check_existing=True)
        if img:
            # Set a consistent name for easier lookup later
            try:
                img.name = img_identifier
            except:
                pass  # Name setting might fail in some contexts
            
            # Generate preview
            img.preview_ensure()
            
            # Pack immediately
            img.pack()
            
            # Delete from disk immediately
            try:
                os.remove(thumb_path)
            except:
                pass  # Don't block if delete fails
        
        return img
    except Exception as e:
        print(f'RPM: image load error: {e}')
        return None

class ReadyPlayerMePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    last_user_id: bpy.props.StringProperty(
        name="Last Authorized User ID",
        default=""
    )
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

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=f"Partner Subdomain: {SUBDOMAIN}")
        col.label(text=f"Last Authorized User ID: {self.last_user_id or '(none)'}")
        wm = context.window_manager
        installed = _is_pywebview_available()
        deps = layout.box()
        r = deps.row(align=True)
        r.label(text="pywebview", icon=('CHECKMARK' if installed else 'CANCEL'))

        box = layout.box()
        box.prop(self, 'login_email')
        box.prop(self, 'login_password')

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

class RPM_OT_OpenMyAvatars(bpy.types.Operator):
    bl_idname = "readyplayerme.open_my_avatars"
    bl_label = "Open My Avatars"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print(f"RPM: OpenMyAvatars.execute entered. PYWEBVIEW_OK={PYWEBVIEW_OK}")
        _installed_now = _is_pywebview_available()
        print(f"RPM: pywebview available now? {_installed_now}")
        if not _installed_now:
            self.report({'ERROR'}, "pywebview is not installed in system Python. Install it in Add-on Preferences.")
            return {'CANCELLED'}

        prefs = bpy.context.preferences.addons[__name__].preferences
        sub = SUBDOMAIN
        print(f"RPM: Opening webview. PYWEBVIEW_OK={PYWEBVIEW_OK}, subdomain={sub}")

        out_fd, out_path = tempfile.mkstemp(prefix='rpm_out_', suffix='.json')
        os.close(out_fd)
        
        # Get the path to the JS injection file
        inject_js_path = os.path.join(os.path.dirname(__file__), 'rpm_inject.js')
        print(f"RPM: JS injection file path: {inject_js_path}")
        
        if not os.path.exists(inject_js_path):
            self.report({'ERROR'}, f"JS injection file not found: {inject_js_path}")
            return {'CANCELLED'}
        
        # Use the existing rpm_webview_helper.py file
        script_path = os.path.join(os.path.dirname(__file__), 'rpm_webview_helper.py')
        print(f"RPM: Helper script path: {script_path}")
        print(f"RPM: Output path: {out_path}")
        
        if not os.path.exists(script_path):
            self.report({'ERROR'}, f"Helper script not found: {script_path}")
            return {'CANCELLED'}

        cmd = _find_system_python_command()
        if not cmd:
            self.report({'ERROR'}, "No system Python found to run webview helper.")
            try:
                os.remove(out_path)
            except Exception:
                pass
            return {'CANCELLED'}

        print(f"RPM: system python command resolved to: {cmd}")
        print(f"RPM: Launching helper: {cmd} -u {script_path}")
        try:
            _env = os.environ.copy()
            try:
                _em = (prefs.login_email or '')
                _pw = (prefs.login_password or '')
                if _em:
                    _env['RPM_WV_EMAIL'] = _em
                if _pw:
                    _env['RPM_WV_PASSWORD'] = _pw
                # Pass the JS file PATH instead of the content
                _env['RPM_INJECT_JS_PATH'] = inject_js_path
                _env['RPM_OUTPUT_PATH'] = out_path
            except Exception as e:
                print(f"RPM: Error setting environment variables: {e}")
            
            proc = subprocess.Popen([cmd, '-u', script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=_env)
            def _reader(p):
                try:
                    for line in p.stdout:
                        print("RPM helper:", line.rstrip())
                except Exception as e:
                    print("RPM helper reader error:", e)
            threading.Thread(target=_reader, args=(proc,), daemon=True).start()
            try:
                print(f"RPM: helper process started pid={proc.pid}")
            except Exception:
                pass
        except Exception as e:
            self.report({'ERROR'}, f"Failed to launch webview helper: {e}")
            try:
                os.remove(out_path)
            except Exception:
                pass
            return {'CANCELLED'}

        rpm_poll_log = {'started': False, 'last': 0.0}

        def poll():
            try:
                if os.path.exists(out_path):
                    try:
                        with open(out_path, 'r', encoding='utf-8') as f:
                            raw_txt = f.read()
                        data = json.loads(raw_txt)
                    except Exception as e:
                        return 1.5
                    evt_type = data.get('type')
                    url = data.get('url')
                    uid = data.get('userId') or ''
                    if evt_type == 'creds':
                        try:
                            p = bpy.context.preferences.addons[__name__].preferences
                            em = (data.get('email') or '').strip()
                            pw = data.get('password') or ''
                            if em:
                                p.login_email = em
                            if pw:
                                p.login_password = pw
                            print("RPM: Saved credentials from Studio sign-in")
                            try:
                                _save_prefs_to_disk(p)
                            except Exception:
                                pass
                            try:
                                bpy.ops.wm.save_userpref()
                            except Exception:
                                pass
                        except Exception:
                            pass
                        try:
                            os.remove(out_path)
                        except Exception:
                            pass
                        return 1.5
                    if evt_type == 'list':
                        try:
                            p = bpy.context.preferences.addons[__name__].preferences
                            p.scraped_avatars_json = json.dumps(data)
                            
                            # Store in persistent collection
                            p.avatar_items.clear()
                            items = data.get('items') or []
                            for it in items:
                                new_item = p.avatar_items.add()
                                new_item.glb_url = it.get('glb') or ''
                                new_item.thumb_url = it.get('thumb') or ''
                                new_item.avatar_id = it.get('id') or ''
                            
                            print(f"RPM: Received and stored {len(items)} avatars")
                            
                            # Pre-load all thumbnails in batch (download, pack, delete)
                            print(f"RPM: Pre-loading {len(items)} thumbnails...")
                            for it in items:
                                thumb = it.get('thumb') or ''
                                aid = it.get('id') or ''
                                if thumb and aid:
                                    try:
                                        _get_or_load_image(thumb, aid)
                                    except Exception:
                                        pass
                            print(f"RPM: All thumbnails loaded and packed")
                            
                            # Save to disk for persistence
                            try:
                                _save_prefs_to_disk(p)
                                print("RPM: Saved avatar data to disk")
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"RPM: Error storing avatars: {e}")
                        try:
                            os.remove(out_path)
                        except Exception:
                            pass
                        print("RPM: poll complete")
                        return None
                    if uid:
                        try:
                            p = bpy.context.preferences.addons[__name__].preferences
                            p.last_user_id = uid
                        except Exception:
                            pass
                    if url:
                        print(f"RPM: Result found. Importing URL: {url}")
                        bpy.ops.import_scene.readyplayerme_importer(model_url=url)
                    try:
                        os.remove(out_path)
                    except Exception:
                        pass
                    if url:
                        print("RPM: poll complete")
                        return None
                    else:
                        return 1.5
                else:
                    try:
                        p = None
                        try:
                            p = proc
                        except Exception:
                            p = None
                        if p is not None:
                            try:
                                if p.poll() is not None:
                                    try:
                                        print(f"RPM: helper process {p.pid} exited; stopping poll")
                                    except Exception:
                                        pass
                                    return None
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if not rpm_poll_log['started']:
                        print("RPM: poll started (1.5s interval)")
                        rpm_poll_log['started'] = True
            except Exception:
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                print("RPM: poll stopped due to error")
                return None
            return 1.5

        try:
            bpy.app.timers.register(poll)
            print("RPM: poll timer registered")
        except Exception as e:
            print("RPM: failed to register poll timer", e)
            return {'CANCELLED'}
        return {'FINISHED'}

class RPM_OT_ImportAvatarURL(bpy.types.Operator):
    bl_idname = "readyplayerme.import_avatar_url"
    bl_label = "Import RPM Avatar by URL"
    bl_options = {'REGISTER', 'UNDO'}
    
    url: bpy.props.StringProperty(default="")
    avatar_id_display: bpy.props.StringProperty(default="")  # For tooltip/description
    quality: bpy.props.EnumProperty(
        items=[('high','High',''),('medium','Medium',''),('low','Low','')],
        default='low'
    )
    t_pose: bpy.props.BoolProperty(default=True)
    arkit_shapes: bpy.props.BoolProperty(default=True)
    enable_texture_atlas: bpy.props.BoolProperty(default=True)
    texture_atlas_size: bpy.props.EnumProperty(
        items=[('none','None',''),('256','256',''),('512','512',''),('1024','1024','')],
        default='1024'
    )
    
    @classmethod
    def description(cls, context, properties):
        aid = properties.avatar_id_display
        if aid:
            return f"Download model {aid}.glb"
        return "Download Ready Player Me avatar"

    def execute(self, context):
        if not self.url:
            self.report({'ERROR'}, "Missing URL")
            return {'CANCELLED'}
        
        # Show which model is being downloaded
        if self.avatar_id_display:
            print(f"RPM: Downloading model {self.avatar_id_display}.glb")
            self.report({'INFO'}, f"Downloading {self.avatar_id_display}.glb...")
        
        try:
            bpy.ops.import_scene.readyplayerme_importer(
                'EXEC_DEFAULT',
                model_url=self.url,
                quality=self.quality,
                t_pose=self.t_pose,
                arkit_shapes=self.arkit_shapes,
                enable_texture_atlas=self.enable_texture_atlas,
                texture_atlas_size=self.texture_atlas_size
            )
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

if __name__ == "__main__":
    register()