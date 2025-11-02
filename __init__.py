bl_info = {
    "name": "ReadyPlayerMe Blender Importer",
    "blender": (2, 80, 0),
    "category": "Import-Export",
    "description": "Import ReadyPlayerMe models into Blender",
    "author": "BeyondDev (Tyler Walker)",
    "version": (1, 0, 56),
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
        data = {
            'email': prefs.login_email or '',
            'password': prefs.login_password or ''
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

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose import mode",
        items=[('MY', "My Avatars", "Use web view to select from your RPM avatars"), ('URL', "From URL", "Import from a GLB URL")],
        default='URL'
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
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        if self.mode == 'URL':
            return self.download_and_import_model(context)
        else:
            return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, 'mode', expand=True)
        if self.mode == 'MY':
            _installed = _is_pywebview_available()
            if not _installed:
                col = layout.column(align=True)
                col.label(text="pywebview is not available. Install it in Add-on Preferences.")
            else:
                layout.operator(RPM_OT_OpenMyAvatars.bl_idname, text="Open My Avatars (Webview)")
                opt = layout.box()
                opt.label(text="Import Options")
                opt.prop(self, 'quality')
                opt.prop(self, 't_pose')
                opt.prop(self, 'arkit_shapes')
                opt.prop(self, 'enable_texture_atlas')
                opt.prop(self, 'texture_atlas_size')
                try:
                    prefs = bpy.context.preferences.addons[__name__].preferences
                    data = json.loads(prefs.scraped_avatars_json or '{}')
                    items = data.get('items') or []
                except Exception:
                    items = []
                if items:
                    gf = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True)
                    for it in items:
                        glb = (it.get('glb') or '')
                        thumb = (it.get('thumb') or '')
                        aid = (it.get('id') or '')
                        icon_id = 0
                        if thumb:
                            icon_id = _get_preview_icon(thumb, aid)
                        op = gf.operator(RPM_OT_ImportAvatarURL.bl_idname, text=aid[:12] or 'Import', icon_value=icon_id)
                        op.url = glb
                        op.quality = self.quality
                        op.t_pose = self.t_pose
                        op.arkit_shapes = self.arkit_shapes
                        op.enable_texture_atlas = self.enable_texture_atlas
                        op.texture_atlas_size = self.texture_atlas_size
        else:
            layout.prop(self, 'model_url')
            col = layout.column(align=True)
            col.prop(self, 'quality')
            col.prop(self, 't_pose')
            col.prop(self, 'arkit_shapes')
            col.prop(self, 'enable_texture_atlas')
            col.prop(self, 'texture_atlas_size')
    
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

    last_user_id: bpy.props.StringProperty(
        name="Last Authorized User ID",
        default=""
    )
    scraped_avatars_json: bpy.props.StringProperty(
        name="Scraped Avatars JSON",
        default=""
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
                            print(f"RPM: Received {len(data.get('items') or [])} avatars")
                        except Exception:
                            pass
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

    def execute(self, context):
        if not self.url:
            self.report({'ERROR'}, "Missing URL")
            return {'CANCELLED'}
        try:
            bpy.ops.import_scene.readyplayerme_importer(
                'EXEC_DEFAULT',
                model_url=self.url,
                mode='URL',
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