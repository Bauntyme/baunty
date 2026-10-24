"""
Frontend Bundler & Minifier for Bauntys Mini App.
Bundles all CSS and JS files, strips comments safely without corrupting strings,
removes sourcemaps, and creates production-ready bundle.min.css, bundle.min.js,
and shield.min.js.
"""
import os
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIR = BASE_DIR / "webapp"
DIST_DIR = WEBAPP_DIR / "dist"

CSS_FILES = [
    "rasxod.css",
    "kaloriya.css",
    "asil.css",
    "kattalar.css",
    "mafia.css",
    "tvroom.css",
    "music.css",
    "docs.css",
    "fx.css",
    "food.css",
    "quiz.css",
    "prava.css",
    "games.css",
    "story.css",
    "books.css",
    "zk.css",
]

JS_FILES = [
    "i18n.js",
    "music.js",
    "docs.js",
    "games.js",
    "kattalar.js",
    "mafia.js",
    "tvroom.js",
    "story.js",
    "books.js",
    "fx.js",
    "food.js",
    "quiz.js",
    "prava.js",
    "rasxod.js",
    "kaloriya.js",
    "asil.js",
    "zk.js",
]

DEVTOOLS_SHIELD_JS = """/* Bauntys Production Security Shield & Anti-Debugging */
(function(){
  "use strict";
  // 1. Silent Console in Production (prevents internal data/endpoint leaks)
  try {
    var noop = function(){};
    var methods = ['log', 'debug', 'info', 'warn', 'error', 'table', 'trace', 'dir', 'dirxml', 'group', 'groupEnd', 'time', 'timeEnd', 'count', 'assert'];
    for (var i = 0; i < methods.length; i++) {
      try { window.console[methods[i]] = noop; } catch(e){}
    }
  } catch(e){}

  // 2. Disable Context Menu (Right Click)
  document.addEventListener("contextmenu", function(e){
    e.preventDefault();
    return false;
  }, {capture: true, passive: false});

  // 3. Block DevTools Shortcuts (F12, Ctrl+Shift+I/J/C/K/E, Ctrl+U, Ctrl+S)
  window.addEventListener("keydown", function(e){
    if (e.keyCode === 123) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
    if (e.ctrlKey && e.shiftKey && (e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67 || e.keyCode === 75 || e.keyCode === 69)) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
    if (e.metaKey && e.altKey && (e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67 || e.keyCode === 85)) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
    if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
      e.preventDefault();
      e.stopPropagation();
      return false;
    }
  }, {capture: true, passive: false});

  // 4. Disable text selection outside input fields
  document.addEventListener("selectstart", function(e){
    var tag = e.target && e.target.tagName;
    if (tag !== "INPUT" && tag !== "TEXTAREA") {
      e.preventDefault();
      return false;
    }
  }, {capture: true, passive: false});

  // 5. Anti-Debugging timing loop & DevTools dock detector
  var antiDebugCheck = function() {
    var t0 = performance.now();
    try {
      (function(){}).constructor("debugger")();
    } catch(e){}
    var t1 = performance.now();
    var devDocked = (window.outerWidth - window.innerWidth > 160) || (window.outerHeight - window.innerHeight > 160);
    if ((t1 - t0 > 100) || devDocked) {
      if (document.body && !window.location.search.includes("debug=1")) {
        try {
          document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#070B1F;color:#fff;font-family:sans-serif;text-align:center;padding:24px;"><h2>🔒 Xavfsizlik nazorati faollashdi.</h2></div>';
        } catch(err){}
      }
    }
  };
  if (typeof window !== "undefined" && !window.location.search.includes("debug=1")) {
    setInterval(antiDebugCheck, 2500);
    window.addEventListener("resize", antiDebugCheck, {passive: true});
  }
})();
"""


def minify_css(css: str) -> str:
    """Minify CSS by stripping comments and redundant whitespace."""
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    css = re.sub(r'[\r\n\t]+', ' ', css)
    css = re.sub(r'\s*([\{\}:;,>~+])\s*', r'\1', css)
    css = re.sub(r';\}', '}', css)
    css = re.sub(r'\s+', ' ', css)
    return css.strip()


def strip_and_clean_js(code: str) -> str:
    """
    Safely strips single-line and multi-line comments while accurately
    preserving string literals ('...', \"...\"), template literals (`...`),
    and regex literals (/.../) without corrupting patterns like 'image/*'.
    """
    code = re.sub(r'//#\s*sourceMappingURL=.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'/\*#\s*sourceMappingURL=.*?\*/', '', code)

    n = len(code)
    i = 0
    out = []
    
    regex_prefixes = {
        '(', '[', '{', ';', ',', '=', ':', '?', '!', '&', '|', '^', '~', '<', '>',
        '+', '-', '*', '/', '%', 'return', 'case', 'throw', 'yield', 'await',
        'delete', 'typeof', 'void', 'do', 'else', 'instanceof', 'in'
    }
    last_sig = ''

    while i < n:
        c = code[i]

        # 1. Single-line comment
        if c == '/' and i + 1 < n and code[i + 1] == '/':
            end = code.find('\n', i + 2)
            if end == -1:
                break
            out.append('\n')
            i = end + 1
            continue

        # 2. Block comment
        if c == '/' and i + 1 < n and code[i + 1] == '*':
            end = code.find('*/', i + 2)
            if end == -1:
                break
            out.append(' ')
            i = end + 2
            continue

        # 3. String literal (' or \")
        if c in ("'", '"'):
            quote = c
            start = i
            i += 1
            while i < n:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                if code[i] == '\n':
                    i += 1
                    break
                i += 1
            token = code[start:i]
            out.append(token)
            last_sig = token
            continue

        # 4. Template literal (`)
        if c == '`':
            start = i
            i += 1
            depth = 0
            while i < n:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == '`' and depth == 0:
                    i += 1
                    break
                if code[i] == '$' and i + 1 < n and code[i + 1] == '{':
                    depth += 1
                    i += 2
                    continue
                if code[i] == '}' and depth > 0:
                    depth -= 1
                    i += 1
                    continue
                i += 1
            token = code[start:i]
            out.append(token)
            last_sig = token
            continue

        # 5. Regex literal (/.../)
        if c == '/' and (last_sig in regex_prefixes or not last_sig):
            start = i
            i += 1
            in_class = False
            while i < n:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == '[':
                    in_class = True
                elif code[i] == ']':
                    in_class = False
                elif code[i] == '/' and not in_class:
                    i += 1
                    while i < n and code[i].isalpha():
                        i += 1
                    break
                elif code[i] == '\n':
                    break
                i += 1
            token = code[start:i]
            out.append(token)
            last_sig = token
            continue

        out.append(c)
        if not c.isspace():
            last_sig = c
        i += 1

    cleaned = ''.join(out)
    
    # Line trimming and empty line collapsing
    lines = []
    for line in cleaned.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        lines.append(trimmed)
    
    return "\n".join(lines).strip()


def build_bundle():
    """Build the production bundle."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Bundling CSS files...")
    css_parts = []
    for cf in CSS_FILES:
        path = WEBAPP_DIR / cf
        if path.exists():
            content = path.read_text(encoding="utf-8")
            css_parts.append(content)
        else:
            print(f"Warning: {cf} not found")
    
    combined_css = "\n".join(css_parts)
    minified_css = minify_css(combined_css)
    
    (DIST_DIR / "bundle.min.css").write_text(minified_css, encoding="utf-8")
    (WEBAPP_DIR / "bundle.min.css").write_text(minified_css, encoding="utf-8")
    print(f"CSS Bundle created: {len(minified_css)} bytes")
    
    print("Bundling JS files...")
    js_parts = [DEVTOOLS_SHIELD_JS]
    for jf in JS_FILES:
        path = WEBAPP_DIR / jf
        if path.exists():
            content = path.read_text(encoding="utf-8")
            cleaned = strip_and_clean_js(content)
            js_parts.append(f";\n{cleaned}\n")
        else:
            print(f"Warning: {jf} not found")
            
    # Extract the main script from index.html (last script tag)
    index_path = WEBAPP_DIR / "index.html"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', index_content, re.DOTALL)
        if scripts and len(scripts) >= 3:
            main_script = scripts[-1].strip()
            if len(main_script) > 5000:
                cleaned_main = strip_and_clean_js(main_script)
                js_parts.append(f";\n{cleaned_main}\n")
    
    combined_js = "\n".join(js_parts)
    
    (DIST_DIR / "bundle.min.js").write_text(combined_js, encoding="utf-8")
    (WEBAPP_DIR / "bundle.min.js").write_text(combined_js, encoding="utf-8")
    print(f"JS Bundle created: {len(combined_js)} bytes")
    
    (DIST_DIR / "shield.min.js").write_text(DEVTOOLS_SHIELD_JS, encoding="utf-8")
    (WEBAPP_DIR / "shield.min.js").write_text(DEVTOOLS_SHIELD_JS, encoding="utf-8")
    print("Shield script created.")

    # Syntax verification if Node.js is present
    try:
        res = subprocess.run(["node", "--check", str(DIST_DIR / "bundle.min.js")], capture_output=True, text=True)
        if res.returncode == 0:
            print("Node.js syntax check on bundle.min.js: PASSED (clean syntax)")
        else:
            print(f"Node.js syntax check FAILED: {res.stderr}")
    except Exception:
        pass


if __name__ == "__main__":
    build_bundle()
