import ast
import os
import sys

def check_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {path}:{e.lineno}: {e}")
        return False

    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue):
            segment = ast.get_source_segment(src, node)
            if segment and '\\' in segment:
                issues.append((node.lineno, segment))
    
    if issues:
        print(f"POTENTIAL Python 3.11 f-string backslash issue in {path}:")
        for lineno, seg in issues:
            print(f"  Line {lineno}: {seg}")
        return False
    return True

def main():
    has_issues = False
    count = 0
    for root, _, files in os.walk('.'):
        if any(ignored in root for ignored in ['.git', '.venv', '__pycache__', '.pytest_cache']):
            continue
        for file in files:
            if file.endswith('.py'):
                count += 1
                if not check_file(os.path.join(root, file)):
                    has_issues = True
    print(f"Checked {count} python files.")
    if has_issues:
        print("Issues found!")
        sys.exit(1)
    else:
        print("All files passed Python 3.11 f-string check!")

if __name__ == '__main__':
    main()
