import webview
import json
import sys
import os
import subprocess
import tempfile
import threading

print('RPM UI helper: starting')

class UIApi:
    def __init__(self):
        self._window = None
        self._addon_name = os.environ.get('RPM_ADDON_NAME', '')
        self._refresh_progress = {'message': 'Idle', 'percent': 0, 'complete': True, 'error': None}
        self._avatars_path = os.environ.get('RPM_AVATARS_PATH', '')
        self._init_email = os.environ.get('RPM_PREFS_EMAIL', '')
        self._init_password = os.environ.get('RPM_PREFS_PASSWORD', '')
        self._defaults = {
            'quality': os.environ.get('RPM_DEFAULT_QUALITY', 'high'),
            't_pose': os.environ.get('RPM_DEFAULT_TPOSE', '1') == '1',
            'arkit_shapes': os.environ.get('RPM_DEFAULT_ARKIT', '1') == '1',
            'enable_texture_atlas': os.environ.get('RPM_DEFAULT_ATLAS', '1') == '1',
            'texture_atlas_size': os.environ.get('RPM_DEFAULT_ATLAS_SIZE', '1024'),
        }
    
    def set_window(self, window):
        self._window = window
    
    def console_log(self, message):
        """Pipe JavaScript console logs to Blender console"""
        try:
            print(f'RPM UI JS> {message}')
            sys.stdout.flush()
        except Exception as e:
            pass
    
    def get_credentials(self):
        """Get saved credentials"""
        try:
            return {'email': self._init_email or '', 'password': self._init_password or ''}
        except Exception as e:
            print(f'RPM UI: get_credentials error: {e}')
            return {'email': '', 'password': ''}
    
    def save_credentials(self, email, password):
        """Save credentials to prefs"""
        try:
            # Write a request file for Blender main process to update AddonPreferences
            addon_dir = os.path.dirname(__file__)
            req_file = os.path.join(addon_dir, 'rpm_prefs_request.json')
            with open(req_file, 'w', encoding='utf-8') as f:
                json.dump({'type': 'save_credentials', 'email': email or '', 'password': password or ''}, f)
            print('RPM UI: Credentials save request written')
            # Update local cached values so UI reflects change immediately
            self._init_email = email or ''
            self._init_password = password or ''
            return True
        except Exception as e:
            print(f'RPM UI: save_credentials error: {e}')
            return False
    
    def logout(self):
        """Clear credentials and avatars"""
        try:
            # Write a logout request file for Blender main process
            addon_dir = os.path.dirname(__file__)
            req_file = os.path.join(addon_dir, 'rpm_prefs_request.json')
            with open(req_file, 'w', encoding='utf-8') as f:
                json.dump({'type': 'logout'}, f)
            print('RPM UI: Logout request written')
            # Update local cached values so UI reflects change immediately
            self._init_email = ''
            self._init_password = ''
            # Clear avatars file if it exists
            if self._avatars_path and os.path.exists(self._avatars_path):
                try:
                    with open(self._avatars_path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    print('RPM UI: Cleared avatars file')
                except Exception as e:
                    print(f'RPM UI: Error clearing avatars file: {e}')
            return True
        except Exception as e:
            print(f'RPM UI: logout error: {e}')
            return False
    
    def get_refresh_progress(self):
        """Get current refresh progress"""
        prog = self._refresh_progress
        
        # Print status updates to Blender console for user visibility
        if prog.get('percent') and not hasattr(self, '_last_reported_percent'):
            self._last_reported_percent = -1
        
        current = prog.get('percent', 0)
        if current != getattr(self, '_last_reported_percent', -1):
            if current in [10, 25, 40, 60, 90, 95, 100]:
                print(f'RPM UI: Refresh progress: {current}%')
                self._last_reported_percent = current
        
        if prog.get('complete'):
            if prog.get('error'):
                print(f'RPM UI: Refresh ERROR: {prog.get("error")}')
            elif prog.get('reload'):
                print('RPM UI: Refresh COMPLETE - Reloading avatars from prefs file')
        
        return prog
    
    def refresh_avatars(self):
        """Open the login webview to refresh avatars - runs synchronously"""
        print('RPM UI: ========================================')
        print('RPM UI: REFRESH AVATARS STARTED')
        print('RPM UI: ========================================')
        
        # Reset progress tracking
        self._last_reported_percent = -1
        
        # Reset progress
        self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': False, 'error': None}
        
        try:
            # Launch the existing RPM webview helper
            addon_dir = os.path.dirname(__file__)
            helper_path = os.path.join(addon_dir, 'rpm_webview_helper.py')
            js_path = os.path.join(addon_dir, 'rpm_inject.js')
            
            # Create temp file for communication
            fd, out_path = tempfile.mkstemp(prefix='rpm_ui_', suffix='.json')
            os.close(fd)
            
            # Progress file for communication
            progress_fd, progress_path = tempfile.mkstemp(prefix='rpm_progress_', suffix='.json')
            os.close(progress_fd)
            
            cmd = self._find_python()
            if not cmd:
                print('RPM UI: No Python command found')
                self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': 'Python not found'}
                return
            
            # Get prefs from env/in-memory (provided by Blender main process)
            email = self._init_email or ''
            password = self._init_password or ''
            
            env = os.environ.copy()
            env['RPM_OUTPUT_PATH'] = out_path
            env['RPM_INJECT_JS_PATH'] = js_path
            env['RPM_WV_EMAIL'] = email
            env['RPM_WV_PASSWORD'] = password
            env['RPM_PROGRESS_PATH'] = progress_path
            
            # Check dev mode from env passed by Blender
            dev_mode = os.environ.get('RPM_DEV_MODE', '0') == '1'
            
            env['RPM_DEV_MODE'] = '1' if dev_mode else '0'
            
            self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 5, 'complete': False, 'error': None}
            
            # Run the webview helper in background thread to not block UI
            def run_helper():
                import time
                
                # Capture child output and forward to this process stdout
                proc = subprocess.Popen(
                    [cmd, helper_path],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=1,
                    universal_newlines=True
                )
                
                def _forward(stream, prefix):
                    try:
                        for line in iter(stream.readline, ''):
                            print(f"{prefix}{line.rstrip()}")
                    except Exception:
                        pass
                
                try:
                    t1 = threading.Thread(target=_forward, args=(proc.stdout, 'RPM helper> '), daemon=True)
                    t2 = threading.Thread(target=_forward, args=(proc.stderr, 'RPM helper ERR> '), daemon=True)
                    t1.start(); t2.start()
                except Exception:
                    pass
                
                print(f'RPM UI: Started helper process PID={proc.pid}')
                sys.stdout.flush()
                
                # Poll for progress updates with timeout
                start_time = time.time()
                timeout = 120  # 2 minute timeout
                last_percent = -1
                
                while proc.poll() is None:
                    # Check timeout
                    if time.time() - start_time > timeout:
                        print('RPM UI: Helper process timeout, terminating...')
                        proc.terminate()
                        self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': 'Timeout after 2 minutes'}
                        return
                    
                    if os.path.exists(progress_path):
                        try:
                            with open(progress_path, 'r', encoding='utf-8') as f:
                                progress_data = json.load(f)
                                percent = progress_data.get('percent', 5)
                                self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': percent, 'complete': False, 'error': None}
                                if percent != last_percent:
                                    print(f'RPM UI: Progress update: {percent}%')
                                    last_percent = percent
                        except Exception as e:
                            # Avoid spamming the console for transient partial writes
                            pass
                    time.sleep(0.2)
                
                # Wait for completion
                return_code = proc.wait()
                print(f'RPM UI: Helper process completed with return code: {return_code}')
                sys.stdout.flush()
                
                self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 95, 'complete': False, 'error': None}
                print(f'RPM UI: Checking for output file: {out_path}')
                sys.stdout.flush()  # Force console output
                
                # Wait a bit for file to be written
                time.sleep(0.5)
                
                # Try multiple times to read the file
                max_attempts = 5
                file_found = False
                for attempt in range(max_attempts):
                    if os.path.exists(out_path):
                        file_found = True
                        print(f'RPM UI: Output file found on attempt {attempt + 1}')
                        break
                    time.sleep(0.2)
                
                # Read the result
                if file_found:
                    try:
                        with open(out_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            print(f'RPM UI: Read data type: {data.get("type")}')
                            if data.get('type') == 'list':
                                items = data.get('items', [])
                                avatar_items = [
                                    {
                                        'glb_url': it.get('glb', ''),
                                        'thumb_url': it.get('thumb', ''),
                                        'avatar_id': it.get('id', '')
                                    } for it in items
                                ]
                                # Update shared avatars file if provided
                                try:
                                    if self._avatars_path:
                                        with open(self._avatars_path, 'w', encoding='utf-8') as af:
                                            json.dump(avatar_items, af, indent=2)
                                        print(f'RPM UI: Wrote {len(avatar_items)} avatars to shared file')
                                    else:
                                        print('RPM UI: No shared avatars path set; avatars will not persist')
                                except Exception as ee:
                                    print(f'RPM UI: Failed to write shared avatars file: {ee}')
                                # Write an update request for Blender main process
                                try:
                                    addon_dir2 = os.path.dirname(__file__)
                                    upd_file = os.path.join(addon_dir2, 'rpm_avatar_update.json')
                                    with open(upd_file, 'w', encoding='utf-8') as uf:
                                        json.dump({'type': 'avatar_update', 'items': avatar_items}, uf)
                                except Exception as ee:
                                    print(f'RPM UI: Failed to write avatar update request: {ee}')
                                
                                # Signal completion with success flag
                                self._refresh_progress = {
                                    'message': 'Retrieving Avatar Data...', 
                                    'percent': 100, 
                                    'complete': True, 
                                    'error': None,
                                    'reload': True  # Signal to reload avatars
                                }
                                print('RPM UI: *** REFRESH COMPLETE - Avatars should reload now ***')
                                sys.stdout.flush()
                            elif data.get('type') == 'error':
                                error_msg = data.get('message', 'Unknown error')
                                self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': error_msg}
                                print(f'RPM UI: Refresh error: {error_msg}')
                                print(f'RPM UI: Error type detected - will show login popup in UI')
                                sys.stdout.flush()
                        
                        try:
                            os.remove(out_path)
                        except:
                            pass
                    except Exception as e:
                        self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': str(e)}
                        print(f'RPM UI: Error reading result: {e}')
                        import traceback
                        traceback.print_exc()
                else:
                    print(f'RPM UI: !!! ERROR - Output file not found after {max_attempts} attempts !!!')
                    print(f'RPM UI: Expected path: {out_path}')
                    sys.stdout.flush()
                    # List files in temp directory
                    try:
                        temp_dir = os.path.dirname(out_path)
                        files = os.listdir(temp_dir)
                        rpm_files = [f for f in files if 'rpm' in f.lower()]
                        print(f'RPM UI: RPM files in temp dir: {rpm_files}')
                        sys.stdout.flush()
                    except Exception as e:
                        print(f'RPM UI: Could not list temp dir: {e}')
                        sys.stdout.flush()
                    self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': 'Output file not created'}
                
                # Cleanup progress file
                try:
                    if os.path.exists(progress_path):
                        os.remove(progress_path)
                except:
                    pass
            
            # Start helper in background thread
            helper_thread = threading.Thread(target=run_helper, daemon=True)
            helper_thread.start()
            print('RPM UI: Background refresh thread started successfully')
            print('RPM UI: Progress updates will appear below as refresh proceeds...')
            
        except Exception as e:
            self._refresh_progress = {'message': 'Retrieving Avatar Data...', 'percent': 0, 'complete': True, 'error': str(e)}
            print(f'RPM UI: refresh_avatars error: {e}')
            import traceback
            traceback.print_exc()
    
    def get_avatars(self):
        """Get current avatars list from prefs"""
        try:
            # Preferred path: read from shared temp file provided by Blender
            if self._avatars_path and os.path.exists(self._avatars_path):
                with open(self._avatars_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f'RPM UI: Loading {len(data)} avatars from shared file')
                    return data
            print('RPM UI: No shared avatars file, returning empty avatar list')
            return []
        except Exception as e:
            print(f'RPM UI: get_avatars error: {e}')
            return []
    
    def get_defaults(self):
        """Get default property values from Blender"""
        try:
            return dict(self._defaults)
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
