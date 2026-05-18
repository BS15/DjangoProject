import os, re
pattern = re.compile(r"""(redirect|reverse)\(['"]([^:^\/]+?)['"]\)""")
pattern_template = re.compile(r"""\{%\s*url\s+['"]([^:^\/]+?)['"]""")

found = {}
for root, dirs, files in os.walk("."):
    if ".venv" in root or ".git" in root or "migrations" in root: continue
    for file in files:
        if file.endswith(".py") or file.endswith(".html"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                for m in pattern.findall(content):
                    if m[1] not in ["admin:index", "login", "logout"]:
                        found.setdefault(m[1], set()).add(path)
                for m in pattern_template.findall(content):
                    if m not in ["admin:index", "login", "logout"]:
                        found.setdefault(m, set()).add(path)

for k, paths in found.items():
    print(f"{k} (found in {len(paths)} files)")
    if 'painel_impostos_view' in k:
        for p in paths:
            print("   -", p)
