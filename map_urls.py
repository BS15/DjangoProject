import os, re
from collections import defaultdict

url_map = defaultdict(list)

for root, dirs, files in os.walk("apps"):
    if "urls.py" in files:
        with open(os.path.join(root, "urls.py"), "r") as f:
            content = f.read()
            app_match = re.search(r"app_name\s*=\s*['\"]([^'\"]+)['\"]", content)
            if app_match:
                app_name = app_match.group(1)
                names = re.findall(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                for n in names:
                    url_map[n].append(app_name)

for name, apps in url_map.items():
    if len(apps) == 1:
        print(f"'{name}': '{apps[0]}:{name}',")
