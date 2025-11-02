(function() {
  var log = function() {};
  
  var dbg = function(s) {
    try {
      window.pywebview.api.on_log(String(s));
    } catch(e) {}
  };
  
  dbg('inject v1.0.46');
  
  function createOverlay() {
    try {
      if(document.getElementById('__rpmOverlay')) return;
      
      var overlay = document.createElement('div');
      overlay.id = '__rpmOverlay';
      overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.85); z-index: 999999; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);';
      
      var message = document.createElement('div');
      message.style.cssText = 'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 50px; border-radius: 16px; font-size: 24px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; box-shadow: 0 20px 60px rgba(0,0,0,0.4); animation: __rpmPulse 2s ease-in-out infinite;';
      message.textContent = 'Please wait, logging you into Ready Player Me';
      
      var style = document.createElement('style');
      style.textContent = '@keyframes __rpmPulse { 0%, 100% { transform: scale(1); box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4); } 50% { transform: scale(1.05); box-shadow: 0 25px 80px rgba(102, 126, 234, 0.6); } }';
      
      overlay.appendChild(message);
      document.head.appendChild(style);
      document.body.appendChild(overlay);
      
      var blockEvent = function(e) {
        if(e.isTrusted) {
          e.preventDefault();
          e.stopPropagation();
          return false;
        }
      };
      
      ['click', 'mousedown', 'mouseup', 'mousemove', 'keydown', 'keypress', 'keyup', 'input', 'change', 'focus', 'blur'].forEach(function(evt) {
        overlay.addEventListener(evt, blockEvent, true);
      });
      
      ['click', 'mousedown', 'mouseup', 'keydown', 'keypress', 'keyup', 'input', 'change'].forEach(function(evt) {
        document.addEventListener(evt, blockEvent, true);
      });
      
      window.__rpmBlockEvents = blockEvent;
      
      dbg('Overlay created and displayed');
    } catch(e) {
      dbg('Overlay creation error: ' + e);
    }
  }
  
  function removeOverlay() {
    try {
      var overlay = document.getElementById('__rpmOverlay');
      if(overlay) {
        overlay.remove();
        
        if(window.__rpmBlockEvents) {
          ['click', 'mousedown', 'mouseup', 'keydown', 'keypress', 'keyup', 'input', 'change'].forEach(function(evt) {
            document.removeEventListener(evt, window.__rpmBlockEvents, true);
          });
          window.__rpmBlockEvents = null;
        }
        
        dbg('Overlay removed');
      }
    } catch(e) {}
  }
  
  var __rpmNativeValueSetter = (function() {
    try {
      return Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    } catch(e) {
      return null;
    }
  })();
  
  var setVal = function(input, v) {
    try {
      if(window.__rpmSetOnceOnly && input.__rpmSetOnce) return;
    } catch(e) {}
    
    try {
      if(__rpmNativeValueSetter) {
        __rpmNativeValueSetter.call(input, v);
      } else {
        input.value = v;
      }
    } catch(e) {
      try {
        input.value = v;
      } catch(_) {}
    }
    
    try {
      input.dispatchEvent(new Event('input', {bubbles:true}));
    } catch(e) {}
    
    try {
      input.dispatchEvent(new Event('change', {bubbles:true}));
    } catch(e) {}
    
    try {
      input.__rpmSetOnce = true;
    } catch(e) {}
  };
  
  function stabilizeInput(input, desired) {
    try {
      try {
        if(window.__rpmDisableStabilizers) return;
      } catch(__) {}
      
      if(!input) return;
      if(input.__rpmStabilized) return;
      
      input.__rpmStabilized = true;
      
      ['input', 'change', 'blur'].forEach(function(ev) {
        input.addEventListener(ev, function() {
          try {
            var want = (typeof desired === 'function') ? desired() : desired;
            if(want && input.value !== want) {
              setVal(input, want);
            }
          } catch(_) {}
        }, true);
      });
    } catch(_) {}
  }
  
  var __rpmStickTimers = new WeakMap();
  
  function stickInputValue(input, desired) {
    try {
      try {
        if(window.__rpmDisableStabilizers) return;
      } catch(__) {}
      
      if(!input) return;
      if(__rpmStickTimers.has(input)) return;
      
      var stable = 0;
      var last = null;
      
      var timer = setInterval(function() {
        try {
          var want = (typeof desired === 'function') ? desired() : desired;
          if(!want) return;
          
          if(input.value !== want) {
            setVal(input, want);
            stable = 0;
          } else {
            if(last === want) {
              stable += 50;
            } else {
              stable = 50;
            }
          }
          
          last = input.value;
          
          if(stable >= 400) {
            clearInterval(timer);
            __rpmStickTimers.delete(input);
          }
        } catch(__) {}
      }, 50);
      
      __rpmStickTimers.set(input, timer);
    } catch(_) {}
  }
  
  var __prefCached = false;
  var __prefE = '';
  var __prefP = '';
  
  function cachePrefs() {
    if(__prefCached) return Promise.resolve({e: __prefE, p: __prefP});
    
    try {
      return window.pywebview.api.get_creds().then(function(c) {
        try {
          __prefE = (c && c.email) || '';
          __prefP = (c && c.password) || '';
          __prefCached = true;
        } catch(_) {}
        return {e: __prefE, p: __prefP};
      });
    } catch(e) {
      return Promise.resolve({e: '', p: ''});
    }
  }
  
  function q(sel) {
    try {
      return document.querySelector(sel);
    } catch(_) {
      return null;
    }
  }
  
  function findEmailInput() {
    return q('input[type=email], input[name=email], input[autocomplete=username], input[id*=email]');
  }
  
  function findPassInput() {
    return q('input[type=password], input[name=password], input[autocomplete=current-password], input[id*=password]');
  }
  
  function typeInto(input, text) {
    try {
      if(!input) return;
      
      try {
        if(window.__rpmTypeOnceOnly && input.__rpmTypedOnce) return;
      } catch(__) {}
      
      if(__rpmNativeValueSetter) {
        __rpmNativeValueSetter.call(input, '');
      } else {
        input.value = '';
      }
      
      for(var i = 0; i < text.length; i++) {
        var ch = text[i];
        
        try {
          input.dispatchEvent(new KeyboardEvent('keydown', {key:ch, bubbles:true}));
        } catch(__) {}
        
        if(__rpmNativeValueSetter) {
          __rpmNativeValueSetter.call(input, input.value + ch);
        } else {
          input.value += ch;
        }
        
        try {
          input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:ch}));
        } catch(__) {
          input.dispatchEvent(new Event('input', {bubbles:true}));
        }
        
        try {
          input.dispatchEvent(new KeyboardEvent('keypress', {key:ch, bubbles:true}));
          input.dispatchEvent(new KeyboardEvent('keyup', {key:ch, bubbles:true}));
        } catch(__) {}
      }
      
      input.dispatchEvent(new Event('change', {bubbles:true}));
      input.dispatchEvent(new Event('blur', {bubbles:true}));
      
      try {
        input.__rpmTypedOnce = true;
      } catch(__) {}
    } catch(_) {}
  }
  
  var __rpmMO = null;
  
  function watchInputs(getE, getP) {
    try {
      try {
        if(window.__rpmDisableStabilizers) return;
      } catch(__) {}
      
      if(__rpmMO) return;
      if(!document || !document.body) return;
      
      var opts = {childList: true, subtree: true};
      
      __rpmMO = new MutationObserver(function() {
        try {
          var em = findEmailInput();
          var pw = findPassInput();
          var e = getE();
          var p = getP();
          
          if(em && e && em.value !== e) {
            setVal(em, e);
            stabilizeInput(em, function() { return e; });
          }
          
          if(pw && p && pw.value !== p) {
            setVal(pw, p);
            stabilizeInput(pw, function() { return p; });
          }
        } catch(__) {}
      });
      
      __rpmMO.observe(document.body, opts);
    } catch(_) {}
  }
  
  function detectManual(input) {
    try {
      if(!input) return;
      
      var flag = function() {
        try {
          window.__rpmManualEntry = true;
          window.__rpmDisableStabilizers = true;
        } catch(__) {}
      };
      
      ['keydown', 'mousedown', 'focus'].forEach(function(ev) {
        try {
          input.addEventListener(ev, flag, {capture: true, once: true});
        } catch(__) {}
      });
    } catch(_) {}
  }
  
  function extractFromMuiP() {
    try {
      var ps = [].slice.call(document.querySelectorAll('p.MuiTypography-root.MuiTypography-body2'));
      for(var i = 0; i < ps.length; i++) {
        var t = (ps[i].textContent || '').trim();
        var m = t.match(/^\s*([a-z0-9-]+)\.readyplayer\.me\s*$/i);
        if(m && m[1]) return m[1];
      }
    } catch(e) {}
    return null;
  }
  
  function extractFromBody() {
    try {
      var t = (document.body && document.body.innerText) || '';
      var m = t.match(/([a-z0-9-]+)\.readyplayer\.me/i);
      if(m && m[1]) return m[1];
    } catch(e) {}
    return null;
  }
  
  function extractFromNextData() {
    try {
      var s = document.getElementById('__NEXT_DATA__');
      if(!s) return null;
      var txt = s.textContent || s.innerText || '';
      var m = txt.match(/([a-z0-9-]+)\.readyplayer\.me/i);
      if(m && m[1]) return m[1];
    } catch(e) {}
    return null;
  }
  
  function extractFromScripts() {
    try {
      var ss = [].slice.call(document.querySelectorAll('script'));
      for(var i = 0; i < ss.length; i++) {
        var txt = ss[i].textContent || ss[i].innerText || '';
        if(!txt) continue;
        var m = txt.match(/([a-z0-9-]+)\.readyplayer\.me/i);
        if(m && m[1]) return m[1];
      }
    } catch(e) {}
    return null;
  }
  
  function extractFromStorage() {
    try {
      for(var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        var v = localStorage.getItem(k) || '';
        var m = (String(k) + ':' + String(v)).match(/([a-z0-9-]+)\.readyplayer\.me/i);
        if(m && m[1]) return m[1];
      }
    } catch(e) {}
    return null;
  }
  
  function isValidSub(s) {
    try {
      var t = String(s || '').toLowerCase();
      if(!t || t === 'undefined' || t === 'null') return null;
      if(!/^[a-z0-9-]+$/.test(t)) return null;
      if(/^(studio|models|www|docs)$/.test(t)) return null;
      return t;
    } catch(e) {
      return null;
    }
  }
  
  function extractFromMuiBoxLink() {
    try {
      var anchors = [].slice.call(document.querySelectorAll('div.MuiBox-root a[href*=".readyplayer.me"]'));
      for(var i = 0; i < anchors.length; i++) {
        var href = anchors[i].href || anchors[i].getAttribute('href') || '';
        var m = href.match(/https?:\/\/([a-z0-9-]+)\.readyplayer\.me/i);
        if(m && m[1]) {
          var v = isValidSub(m[1]);
          if(v) return v;
        }
        var txt = (anchors[i].textContent || '').trim();
        var m2 = txt.match(/([a-z0-9-]+)\.readyplayer\.me/i);
        if(m2 && m2[1]) {
          var v2 = isValidSub(m2[1]);
          if(v2) return v2;
        }
      }
    } catch(e) {}
    return null;
  }
  
  function extractSub() {
    try {
      var cached = (window.__rpmSub && typeof window.__rpmSub === 'string') ? window.__rpmSub : '';
      var validCached = isValidSub(cached);
      if(validCached) return validCached;
      
      var re = /([a-z0-9-]+)\.readyplayer\.me/i;
      
      // Prefer the explicit typography text first (matches the dashboard card text)
      var mp = extractFromMuiP();
      if(isValidSub(mp)) {
        window.__rpmSub = mp;
        dbg('extractSub from MUI P: ' + mp);
        return mp;
      }
      
      // Then try the anchor link inside the dashboard card
      var box = extractFromMuiBoxLink();
      if(isValidSub(box)) {
        window.__rpmSub = box;
        dbg('extractSub from MUI Box link: ' + box);
        return box;
      }
      
      var nodes = [].slice.call(document.querySelectorAll('p, a, span, div'));
      for(var i = 0; i < nodes.length; i++) {
        var t = (nodes[i].textContent || '');
        var m = t.match(re);
        if(m && m[1]) {
          var v = isValidSub(m[1]);
          if(v) {
            window.__rpmSub = v;
            dbg('extractSub from text: ' + v);
            return v;
          }
        }
      }
      
      var as = [].slice.call(document.querySelectorAll('a[href]'));
      for(var j = 0; j < as.length; j++) {
        var h = as[j].href || as[j].getAttribute('href') || '';
        var m2 = h.match(re);
        if(m2 && m2[1]) {
          var v2 = isValidSub(m2[1]);
          if(v2) {
            window.__rpmSub = v2;
            dbg('extractSub from href: ' + v2);
            return v2;
          }
        }
      }
      
      var sc = extractFromScripts();
      if(isValidSub(sc)) {
        window.__rpmSub = sc;
        dbg('extractSub from scripts: ' + sc);
        return sc;
      }
      
      var st = extractFromStorage();
      if(isValidSub(st)) {
        window.__rpmSub = st;
        dbg('extractSub from storage: ' + st);
        return st;
      }
      
      var nd = extractFromNextData();
      if(isValidSub(nd)) {
        window.__rpmSub = nd;
        dbg('extractSub from NEXT_DATA: ' + nd);
        return nd;
      }
      
      var bd = extractFromBody();
      if(isValidSub(bd)) {
        window.__rpmSub = bd;
        dbg('extractSub from body: ' + bd);
        return bd;
      }
    } catch(e) {}
    return null;
  }
  
  function collect() {
    var imgs = [].slice.call(document.querySelectorAll('img'));
    var out = [];
    var seen = {};
    
    for(var i = 0; i < imgs.length; i++) {
      var src = imgs[i].currentSrc || imgs[i].src || '';
      var m = src && src.match(/https?:\/\/models\.readyplayer\.me\/([a-f0-9]+)\.png/i);
      if(m) {
        var id = m[1];
        if(seen[id]) continue;
        seen[id] = 1;
        out.push({
          id: id,
          thumb: src,
          glb: 'https://models.readyplayer.me/' + id + '.glb'
        });
      }
    }
    return out;
  }
  
  function sendCreds(e, p) {
    try {
      window.pywebview.api.on_creds({email: (e || ''), password: (p || '')});
      window.__rpmCredsCaptured = true;
      dbg('Captured credentials: email=' + (e || '(none)'));
    } catch(_) {}
  }
  
  function attachStudioCapture() {
    try {
      var emailInput = document.querySelector('input[type=email], input[name=email]');
      var passInput = document.querySelector('input[type=password], input[name=password]');
      
      if(emailInput) {
        emailInput.addEventListener('input', function(ev) {
          try {
            if(!window.__rpmAutofilling) {
              window.__rpmEmail = ev.target.value;
            }
          } catch(_) {}
        });
        if(emailInput.value) window.__rpmEmail = emailInput.value;
      }
      
      if(passInput) {
        passInput.addEventListener('input', function(ev) {
          try {
            if(!window.__rpmAutofilling) {
              window.__rpmPass = ev.target.value;
            }
          } catch(_) {}
        });
        if(passInput.value) window.__rpmPass = passInput.value;
      }
      
      var form = (emailInput && emailInput.closest('form')) || (passInput && passInput.closest('form')) || document.querySelector('form');
      
      if(form && !form.__rpmHooked) {
        form.__rpmHooked = true;
        form.addEventListener('submit', function() {
          var finalEmail = (emailInput && emailInput.value) || window.__rpmEmail || '';
          var finalPass = (passInput && passInput.value) || window.__rpmPass || '';
          dbg('Form submit captured: email=' + finalEmail);
          sendCreds(finalEmail, finalPass);
        }, true);
      }
      
      if((window.__rpmEmail == null || window.__rpmEmail === '') && emailInput && emailInput.value) {
        window.__rpmEmail = emailInput.value;
      }
      
      if((window.__rpmPass == null || window.__rpmPass === '') && passInput && passInput.value) {
        window.__rpmPass = passInput.value;
      }
      
      try {
        window.pywebview.api.get_creds().then(function(c) {
          try {
            var e = c && c.email || '';
            var p = c && c.password || '';
            
            if(e && p) {
              if(emailInput && !emailInput.value) {
                emailInput.value = e;
                emailInput.dispatchEvent(new Event('input', {bubbles:true}));
                window.__rpmEmail = e;
              }
              if(passInput && !passInput.value) {
                passInput.value = p;
                passInput.dispatchEvent(new Event('input', {bubbles:true}));
                window.__rpmPass = p;
              }
            }
          } catch(_) {}
        });
      } catch(_) {}
      
      return !!emailInput;
    } catch(e) {
      dbg('attachStudioCapture error: ' + e);
      return false;
    }
  }
  
  function onSubSignin() {
    try {
      if(window.__rpmDidSubmitSub) return;
      
      cachePrefs().then(function(pr) {
        try {
          var e = pr.e || '';
          var pp = pr.p || '';
          
          if(!e && window.__rpmEmail) e = window.__rpmEmail;
          if(!pp && window.__rpmPass) pp = window.__rpmPass;
          
          var emailInput = findEmailInput();
          var passInput = findPassInput();
          var form = (emailInput && emailInput.closest('form')) || (passInput && passInput.closest('form')) || document.querySelector('form');
          
          if(!(e && pp)) {
            dbg('Subdomain creds incomplete; skipping autofill');
            return;
          }
          
          if(!window.__rpmDidSubmitSub) {
            window.__rpmDidSubmitSub = true;
            
            dbg('Starting subdomain authorize login sequence');
            dbg('Email input found: ' + !!emailInput);
            dbg('Password input found: ' + !!passInput);
            
            if(!emailInput) {
              dbg('ERROR: No email input found on subdomain page!');
              window.__rpmDidSubmitSub = false;
              return;
            }
            if(!passInput) {
              dbg('ERROR: No password input found on subdomain page!');
              window.__rpmDidSubmitSub = false;
              return;
            }
            
            setTimeout(function() {
              try {
                emailInput.click();
                dbg('Email input clicked');
                
                setTimeout(function() {
                  try {
                    typeInto(emailInput, e);
                    dbg('Subdomain email typed: ' + e);
                      
                      setTimeout(function() {
                        try {
                          passInput.click();
                          dbg('Password input clicked');
                          
                          setTimeout(function() {
                            try {
                              typeInto(passInput, pp);
                              dbg('Subdomain password typed (length: ' + pp.length + ')');
                              
                              setTimeout(function() {
                                  try {
                                    dbg('Attempting subdomain form submission');
                                    
                                    var submit = form && form.querySelector('button[type=submit]');
                                    if(submit) {
                                      var disabled = submit.disabled || submit.getAttribute('aria-disabled') === 'true';
                                      var style = getComputedStyle(submit);
                                      var visible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                                      
                                      if(!disabled && visible) {
                                        dbg('Clicking subdomain submit button');
                                        submit.click();
                                        
                                        createOverlay();
                                        
                                        setTimeout(function() {
                                          try {
                                            var host = location.host;
                                            var choose = 'https://' + host + '/avatar/choose';
                                            if(location.pathname !== '/avatar/choose') {
                                              dbg('Redirecting to choose page: ' + choose);
                                              location.href = choose;
                                            }
                                          } catch(__) {}
                                        }, 1000);
                                      } else {
                                        dbg('Submit button disabled or hidden, trying form.requestSubmit()');
                                        if(form && form.requestSubmit) {
                                          form.requestSubmit();
                                        }
                                      }
                                    } else {
                                      dbg('No submit button found, using form.requestSubmit()');
                                      if(form && form.requestSubmit) {
                                        form.requestSubmit();
                                      } else if(form) {
                                        form.submit();
                                      }
                                    }
                                  } catch(err) {
                                    dbg('Subdomain submit error: ' + err);
                                  }
                              }, 150);
                            } catch(err) {
                              dbg('Subdomain password typing error: ' + err);
                            }
                          }, 50);
                        } catch(err) {
                          dbg('Subdomain password click error: ' + err);
                        }
                      }, 100);
                    } catch(err) {
                      dbg('Subdomain email typing error: ' + err);
                    }
                  }, 50);
              } catch(err) {
                dbg('Subdomain email click error: ' + err);
              }
            }, 100);
          }
        } catch(err) {
          dbg('onSubSignin inner error: ' + err);
        }
      });
    } catch(e) {
      dbg('onSubSignin error: ' + e);
    }
  }
  
  function loop() {
    try {
      window.__rpmLastLoopTime = Date.now();
      setTimeout(loop, 800);
      var h = location.host;
      var p = location.pathname;
      try {
        var now = Date.now();
        var last = window.__rpmLastHP || {h:'', p:'', t:0};
        if(last.h !== h || last.p !== p || (now - last.t) > 5000) {
          dbg('host=' + h + ' path=' + p);
          window.__rpmLastHP = {h:h, p:p, t: now};
        }
      } catch(__) {
        dbg('host=' + h + ' path=' + p);
      }
      
      if(h === 'studio.readyplayer.me') {
        attachStudioCapture();
        
        if(p.indexOf('/signin') === 0) {
          try {
            cachePrefs().then(function(pr) {
              try {
                var e = pr.e || '';
                var pp = pr.p || '';
                var emailInput = findEmailInput();
                var passInput = findPassInput();
                var form = (emailInput && emailInput.closest('form')) || (passInput && passInput.closest('form')) || document.querySelector('form');
                
                detectManual(emailInput);
                detectManual(passInput);
                
                if(!(e && pp)) {
                  dbg('Prefs incomplete; skip Studio autofill');
                  window.__rpmDisableStabilizers = true;
                  return;
                }
                
                if(!window.__rpmStudioFilled) {
                  window.__rpmStudioFilled = true;
                  window.__rpmDisableStabilizers = true;
                  window.__rpmAutofilling = true;
                  
                  dbg('Starting Studio login sequence');
                  
                  setTimeout(function() {
                    try {
                      if(emailInput) {
                        emailInput.click();
                        
                        setTimeout(function() {
                          try {
                            typeInto(emailInput, e);
                            window.__rpmEmail = e;
                            dbg('Email typed: ' + e);
                            
                            setTimeout(function() {
                              try {
                                if(passInput) {
                                  passInput.click();
                                  
                                  setTimeout(function() {
                                    try {
                                      typeInto(passInput, pp);
                                      window.__rpmPass = pp;
                                      dbg('Password typed (length: ' + pp.length + ')');
                                      
                                      window.__rpmAutofilling = false;
                                      
                                      setTimeout(function() {
                                        try {
                                          dbg('Attempting form submission');
                                          dbg('Email field value: ' + (emailInput ? emailInput.value : 'N/A'));
                                          dbg('Password field length: ' + (passInput ? passInput.value.length : 'N/A'));
                                          
                                          var submit = form && form.querySelector('button[type=submit]');
                                          if(submit) {
                                            var disabled = submit.disabled || submit.getAttribute('aria-disabled') === 'true';
                                            var style = getComputedStyle(submit);
                                            var visible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                                            dbg('Submit button found - disabled: ' + disabled + ', visible: ' + visible);
                                            
                                            if(!disabled && visible) {
                                              dbg('Clicking submit button');
                                              submit.click();
                                              
                                              setTimeout(function() {
                                                try {
                                                  if(!window.__rpmOverlayShown) {
                                                    window.__rpmOverlayShown = true;
                                                    createOverlay();
                                                  }
                                                } catch(__) {}
                                              }, 500);
                                              
                                              setTimeout(function() {
                                                try {
                                                  if(location.pathname === '/signin') {
                                                    dbg('Still on signin page after 2s - checking for errors');
                                                    var errorEls = document.querySelectorAll('[role=alert], .error, [class*=error], [class*=Error]');
                                                    if(errorEls.length > 0) {
                                                      for(var i = 0; i < errorEls.length; i++) {
                                                        var txt = (errorEls[i].textContent || '').trim();
                                                        if(txt) dbg('Error message found: ' + txt);
                                                      }
                                                    }
                                                  }
                                                } catch(_) {}
                                              }, 2000);
                                            } else {
                                              dbg('Submit button is disabled or hidden, trying form.requestSubmit()');
                                              if(form && form.requestSubmit) {
                                                form.requestSubmit();
                                              }
                                            }
                                          } else {
                                            dbg('No submit button found, using form.requestSubmit()');
                                            if(form && form.requestSubmit) {
                                              form.requestSubmit();
                                            } else if(form) {
                                              dbg('Using form.submit()');
                                              form.submit();
                                            }
                                          }
                                        } catch(err) {
                                          dbg('Submit error: ' + err);
                                        }
                                      }, 150);
                                    } catch(err) {
                                      dbg('Password typing error: ' + err);
                                    }
                                  }, 50);
                                }
                              } catch(err) {
                                dbg('Password click error: ' + err);
                              }
                            }, 100);
                          } catch(err) {
                            dbg('Email typing error: ' + err);
                          }
                        }, 50);
                      }
                    } catch(err) {
                      dbg('Email click error: ' + err);
                    }
                  }, 100);
                }
              } catch(err) {
                dbg('autoStudio error: ' + err);
              }
            });
          } catch(_) {}
          return;
        }
        
        if(!window.__rpmStudioLoadedAt) {
          window.__rpmStudioLoadedAt = Date.now();
          dbg('Studio dashboard detected, waiting 0.5s before redirect');
          return;
        }
        
        var elapsed = Date.now() - window.__rpmStudioLoadedAt;
        if(elapsed < 500) {
          return;
        }
        
        var sub = extractSub();
        if(!sub) {
          dbg('No subdomain detected yet, continuing to wait');
          return;
        }
        
        if(!window.__rpmDidRedirectToSub) {
          window.__rpmDidRedirectToSub = true;
          var target = 'https://' + sub + '.readyplayer.me/avatar/authorize';
          dbg('Dashboard loaded, redirecting to subdomain authorize: ' + target);
          location.href = target;
        }
        return;
      } else if(/\.readyplayer\.me$/.test(h) && (p.indexOf('/avatar/authorize') === 0 || p.indexOf('/avatar/signin') === 0)) {
        onSubSignin();
      } else if(/\.readyplayer\.me$/.test(h) && p.indexOf('/avatar/choose') === 0) {
        removeOverlay();
        var list = collect();
        if(list && list.length) {
          try {
            window.pywebview.api.on_list({type: 'list', items: list});
            dbg('Avatar list sent, closing window in 1s...');
            setTimeout(function() {
              try {
                window.pywebview.api.close_window();
              } catch(__) {}
            }, 1000);
          } catch(_) {}
          return;
        }
      } else if(/\.readyplayer\.me$/.test(h) && p.indexOf('/avatar') === 0) {
        var list = collect();
        if(list && list.length) {
          try {
            window.pywebview.api.on_list({type: 'list', items: list});
            dbg('Avatar list sent, closing window in 1s...');
            setTimeout(function() {
              try {
                window.pywebview.api.close_window();
              } catch(__) {}
            }, 1000);
          } catch(_) {}
          return;
        }
      }
    } catch(e) {
      dbg('loop error: ' + e);
    }
  }
  
  cachePrefs().then(function(pr) {
    try {
      var hasEmail = !!(pr && pr.e);
      var hasPass = !!(pr && pr.p);
      if(hasEmail && hasPass) {
        dbg('Credentials found at start, showing overlay immediately');
        window.__rpmOverlayShown = true;
        setTimeout(function() {
          createOverlay();
        }, 500);
      }
    } catch(__) {}
  });
  
  if(!window.__rpmLoopStarted) {
    window.__rpmLoopStarted = true;
    dbg('Starting main loop');
    loop();
  } else {
    var timeSinceLastLoop = window.__rpmLastLoopTime ? (Date.now() - window.__rpmLastLoopTime) : 9999;
    if(timeSinceLastLoop > 2000) {
      dbg('Loop stopped (last ran ' + timeSinceLastLoop + 'ms ago), restarting');
      loop();
    } else {
      dbg('Loop already running, skipping duplicate start');
    }
  }
})();