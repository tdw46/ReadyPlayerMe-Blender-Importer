import webview
import json
import sys
import os
import subprocess
import tempfile

print('RPM UI helper: starting')

class UIApi:
    def __init__(self):
        self._window = None
        self._addon_name = os.environ.get('RPM_ADDON_NAME', '')
    
    def set_window(self, window):
        self._window = window
    
    def refresh_avatars(self):
        """Open the login webview to refresh avatars"""
        print('RPM UI: refresh_avatars called')
        try:
            # Launch the existing RPM webview helper
            addon_dir = os.path.dirname(__file__)
            helper_path = os.path.join(addon_dir, 'rpm_webview_helper.py')
            js_path = os.path.join(addon_dir, 'rpm_inject.js')
            
            # Create temp file for communication
            fd, out_path = tempfile.mkstemp(prefix='rpm_ui_', suffix='.json')
            os.close(fd)
            
            cmd = self._find_python()
            if not cmd:
                print('RPM UI: No Python command found')
                return
            
            # Get prefs
            prefs_file = os.path.join(addon_dir, 'rpm_prefs.json')
            email = ''
            password = ''
            if os.path.exists(prefs_file):
                try:
                    with open(prefs_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        email = data.get('email', '')
                        password = data.get('password', '')
                except:
                    pass
            
            env = os.environ.copy()
            env['RPM_OUTPUT_PATH'] = out_path
            env['RPM_INJECT_JS_PATH'] = js_path
            env['RPM_WV_EMAIL'] = email
            env['RPM_WV_PASSWORD'] = password
            
            # Run the webview helper
            proc = subprocess.Popen(
                [cmd, helper_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for it to finish
            proc.wait()
            
            # Read the result
            if os.path.exists(out_path):
                try:
                    with open(out_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('type') == 'list':
                            items = data.get('items', [])
                            # Save to prefs
                            avatar_items = []
                            for it in items:
                                avatar_items.append({
                                    'glb_url': it.get('glb', ''),
                                    'thumb_url': it.get('thumb', ''),
                                    'avatar_id': it.get('id', '')
                                })
                            
                            # Update prefs file
                            prefs_data = {}
                            if os.path.exists(prefs_file):
                                try:
                                    with open(prefs_file, 'r', encoding='utf-8') as f:
                                        prefs_data = json.load(f)
                                except:
                                    pass
                            
                            prefs_data['avatar_items'] = avatar_items
                            
                            with open(prefs_file, 'w', encoding='utf-8') as f:
                                json.dump(prefs_data, f)
                            
                            print(f'RPM UI: Saved {len(avatar_items)} avatars')
                            
                            # Update the UI
                            if self._window:
                                js = f'updateAvatarsList({json.dumps(avatar_items)});'
                                self._window.evaluate_js(js)
                    
                    os.remove(out_path)
                except Exception as e:
                    print(f'RPM UI: Error reading result: {e}')
        except Exception as e:
            print(f'RPM UI: refresh_avatars error: {e}')
    
    def get_avatars(self):
        """Get current avatars list from prefs"""
        try:
            addon_dir = os.path.dirname(__file__)
            prefs_file = os.path.join(addon_dir, 'rpm_prefs.json')
            
            if os.path.exists(prefs_file):
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('avatar_items', [])
            return []
        except Exception as e:
            print(f'RPM UI: get_avatars error: {e}')
            return []
    
    def get_defaults(self):
        """Get default property values from Blender"""
        try:
            addon_dir = os.path.dirname(__file__)
            defaults_file = os.path.join(addon_dir, 'rpm_ui_defaults.json')
            
            if os.path.exists(defaults_file):
                with open(defaults_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Fallback defaults
            return {
                'quality': 'high',
                't_pose': True,
                'arkit_shapes': True,
                'enable_texture_atlas': True,
                'texture_atlas_size': '1024'
            }
        except Exception as e:
            print(f'RPM UI: get_defaults error: {e}')
            return {}
    
    def download_avatar(self, options):
        """Trigger download in Blender"""
        print(f'RPM UI: download_avatar called with options: {options}')
        try:
            # Create a temp file with download request
            addon_dir = os.path.dirname(__file__)
            req_file = os.path.join(addon_dir, 'rpm_download_request.json')
            
            with open(req_file, 'w', encoding='utf-8') as f:
                json.dump(options, f)
            
            print(f'RPM UI: Download request written to {req_file}')
        except Exception as e:
            print(f'RPM UI: download_avatar error: {e}')
    
    def close_window(self):
        """Close the webview window"""
        print('RPM UI: close_window called')
        try:
            if self._window:
                self._window.destroy()
        except Exception as e:
            print(f'RPM UI: close_window error: {e}')
    
    def _find_python(self):
        candidates = ['py', 'python', 'python3'] if sys.platform.startswith('win') else ['python3', 'python']
        import shutil
        for cmd in candidates:
            if shutil.which(cmd):
                return cmd
        return None


def on_loaded():
    """Called when the webview page is loaded"""
    print('RPM UI helper: page loaded, dispatching pywebviewready event')

def main():
    html_path = os.environ.get('RPM_HTML_PATH', '')
    if not html_path or not os.path.exists(html_path):
        print(f'RPM UI helper: ERROR - HTML file not found: {html_path}')
        sys.exit(1)
    
    print(f'RPM UI helper: Loading HTML from {html_path}')
    
    api = UIApi()
    
    window = webview.create_window(
        'Ready Player Me - Blender Importer',
        html_path,
        width=900,
        height=800,
        js_api=api
    )
    
    api.set_window(window)
    
    try:
        if sys.platform == 'win32':
            print('RPM UI helper: starting webview with edgechromium')
            webview.start(on_loaded, gui='edgechromium', debug=False)
        else:
            print('RPM UI helper: starting webview default gui')
            webview.start(on_loaded, debug=False)
    except Exception as e:
        print(f'RPM UI helper: webview.start error: {e}')
        webview.start(on_loaded, debug=False)


if __name__ == '__main__':
    main()
