import webview
import json
import sys
import os
import threading
import time

print('RPM helper: starting')
sys.stdout.flush()

class API:
    def __init__(self, outpath, progress_path=None):
        self.outpath = outpath
        self.progress_path = progress_path
        self._email = ''
        self._password = ''
        
    def _atomic_write_json(self, path, payload):
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            print('RPM helper: atomic write failed for', path, e)
    
    def update_progress(self, percent):
        """Write progress update to file"""
        if self.progress_path:
            try:
                self._atomic_write_json(self.progress_path, {'percent': percent})
            except Exception as e:
                print(f'RPM helper: Failed to write progress: {e}')
    
    def on_list(self, payload):
        print(f'RPM helper: on_list called with payload type: {type(payload)}')
        sys.stdout.flush()
        try:
            if isinstance(payload, dict):
                items_count = len(payload.get('items', []))
                print(f'RPM helper: Writing {items_count} items to {self.outpath}')
                sys.stdout.flush()
                self._atomic_write_json(self.outpath, payload)
                print(f'RPM helper: Successfully wrote output file')
                sys.stdout.flush()
            else:
                print(f'RPM helper: Payload is not a dict: {payload}')
                sys.stdout.flush()
        except Exception as e:
            print(f'RPM helper: on_list error: {e}')
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
        try:
            print('RPM helper: Destroying window...')
            sys.stdout.flush()
            webview.destroy_window()
        except Exception as e:
            print(f'RPM helper: destroy_window error: {e}')
            sys.stdout.flush()
        # Ensure helper terminates so the parent doesn't time out
        try:
            print('RPM helper: exiting process')
            sys.stdout.flush()
            sys.exit(0)
        except SystemExit:
            pass
    
    def on_log(self, s):
        try:
            print('RPM helper log:', s)
        except Exception:
            pass
    
    def on_creds(self, payload):
        try:
            if isinstance(payload, dict):
                self._email = (payload.get('email') or '').strip()
                self._password = payload.get('password') or ''
            print('RPM helper: creds received')
            try:
                with open(self.outpath, 'w', encoding='utf-8') as f:
                    json.dump({'type': 'creds', 'email': self._email, 'password': self._password}, f)
            except Exception as e:
                print('RPM helper: failed to write creds', e)
        except Exception as e:
            print('RPM helper: on_creds error', e)
    
    def get_creds(self):
        try:
            return {'email': self._email, 'password': self._password}
        except Exception:
            return {'email': '', 'password': ''}
    
    def close_window(self):
        try:
            print('RPM helper: close_window called, destroying window...')
            webview.windows[0].destroy()
        except Exception as e:
            print('RPM helper: close_window error', e)


def start_inject(w, dev_mode=True):
    js_path = os.environ.get('RPM_INJECT_JS_PATH', '')
    if not js_path:
        print('RPM helper: WARNING - No JS file path provided')
        return
    
    if not os.path.exists(js_path):
        print('RPM helper: ERROR - JS file not found at:', js_path)
        return
    
    # Minimize window if not in dev mode (called after window is ready)
    if not dev_mode:
        try:
            w.minimize()
            print('RPM helper: window minimized (non-dev mode)')
        except Exception as e:
            print('RPM helper: minimize error', e)
    
    try:
        with open(js_path, 'r', encoding='utf-8') as f:
            js_code = f.read()
        print('RPM helper: Loaded', len(js_code), 'chars of JS from file')
    except Exception as e:
        print('RPM helper: Failed to read JS file:', e)
        return
    
    inject_count = {'count': 0}
    last_url = {'url': ''}
    
    def inject():
        try:
            inject_count['count'] += 1
            print(f'RPM helper: Injecting JS into webview (injection #{inject_count["count"]})')
            w.evaluate_js(js_code)
            print('RPM helper: JS injection successful')
        except Exception as e:
            print('RPM helper: inject error', e)
    
    def poll_navigation():
        while True:
            try:
                time.sleep(0.5)
                current_url = w.get_current_url()
                if current_url and current_url != last_url['url']:
                    print(f'RPM helper: Navigation detected: {current_url}')
                    last_url['url'] = current_url
                    time.sleep(0.3)
                    inject()
            except Exception as e:
                break
    
    try:
        w.events.loaded += inject
    except Exception as e:
        print('RPM helper: cannot attach loaded event', e)
    
    inject()
    
    nav_thread = threading.Thread(target=poll_navigation, daemon=True)
    nav_thread.start()


def main(outpath):
    print('RPM helper: creating window')
    print('RPM helper: output path', outpath)
    
    progress_path = os.environ.get('RPM_PROGRESS_PATH', '')
    api = API(outpath, progress_path)
    
    try:
        api._email = os.environ.get('RPM_WV_EMAIL', '')
        api._password = os.environ.get('RPM_WV_PASSWORD', '')
        if api._email:
            print('RPM helper: Loaded email from env:', api._email)
    except Exception:
        pass
    
    # Check dev mode
    dev_mode = os.environ.get('RPM_DEV_MODE', '0') == '1'
    print(f'RPM helper: dev_mode = {dev_mode}')
    
    w = webview.create_window(
        'Ready Player Me',
        url='https://studio.readyplayer.me/signin',
        width=1000,
        height=800,
        js_api=api,
        hidden=False
    )
    
    try:
        if sys.platform == 'win32':
            print('RPM helper: starting webview with edgechromium')
            webview.start(start_inject, (w, dev_mode), gui='edgechromium', debug=False)
        else:
            print('RPM helper: starting webview default gui')
            webview.start(start_inject, (w, dev_mode), debug=False)
    except Exception as e:
        print('RPM helper: webview.start error', e)
        webview.start(start_inject, (w, dev_mode), debug=False)


if __name__ == '__main__':
    output_path = os.environ.get('RPM_OUTPUT_PATH', '')
    if not output_path:
        print('RPM helper: ERROR - No output path provided')
        sys.exit(1)
    main(output_path)