import os, re
from collections import defaultdict

# 1. Mapear URLs ativas (name -> app_name:name)
url_map = defaultdict(list)
# Adicionar mapeamentos manuais para sufixos/nomes que mudaram
manual_map = {
    'gerenciar_credor_view': 'cadastros:credor_detail',
    'add_credor_view': 'cadastros:credor_create',
    'gerenciar_suprimento_view': 'suprimentos:suprimento_detail',
    'add_suprimento_view': 'suprimentos:suprimento_create',
    'editar_processo_verbas_capa': 'verbas_indenizatorias:processo_verbas_edit_capa',
    'editar_processo_verbas_pendencias': 'verbas_indenizatorias:processo_verbas_edit_pendencias',
    'editar_processo_verbas_documentos': 'verbas_indenizatorias:processo_verbas_edit_documentos',
    'editar_processo_verbas': 'verbas_indenizatorias:processo_verbas_detail',
    'cancelar_suprimento_spoke_view': 'suprimentos:cancelar_suprimento_action',
    'editar_processo': 'pagamentos:processo_detail',
    'painel_impostos_view': 'retencoes:impostos_list',
    'add_diaria': 'verbas_indenizatorias:diaria_create',
    'gerenciar_diaria': 'verbas_indenizatorias:diaria_detail',
    'importar_diarias': 'verbas_indenizatorias:importar_diarias',
    'sincronizar_diarias': 'verbas_indenizatorias:sincronizar_diarias',
    'edit_reembolso': 'verbas_indenizatorias:reembolso_edit',
    'gerenciar_jeton': 'verbas_indenizatorias:jeton_detail',
    'gerenciar_auxilio': 'verbas_indenizatorias:auxilio_detail',
    'gerenciar_reembolso': 'verbas_indenizatorias:reembolso_detail',
    'gerenciar_prestacao': 'verbas_indenizatorias:prestacao_detail',
    'edit_auxilio': 'verbas_indenizatorias:auxilio_edit',
}

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

final_map = {}
for name, apps in url_map.items():
    if len(apps) == 1:
        final_map[name] = f"{apps[0]}:{name}"

final_map.update(manual_map)

# Variantes de gerenciar/editar que perderam "view"
for key in list(final_map.keys()):
    if key.endswith('_view'):
        base = key[:-5]
        if base not in final_map:
            final_map[base] = final_map[key]
    elif key.endswith('_action'):
        base = key[:-7]
        if base not in final_map:
            final_map[base] = final_map[key]

# 2. Encontrar e substituir nos arquivos
pattern = re.compile(r"(redirect|reverse)\(['\"]([^:^\/]+?)['\"]")
pattern_template = re.compile(r"\{%\s*url\s+['\"]([^:^\/]+?)['\"]")

total_fixes = 0

for root, dirs, files in os.walk("."):
    if ".venv" in root or ".git" in root or "migrations" in root: continue
    for file in files:
        if file.endswith(".py") or file.endswith(".html"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = content
            
            # Python replaces
            for match in pattern.finditer(content):
                func, name = match.groups()
                if name in ["admin:index", "login", "logout"]: continue
                if name in final_map:
                    # Substitui chamadas exatas
                    old_str = f"{func}('{name}'"
                    new_str = f"{func}('{final_map[name]}'"
                    new_content = new_content.replace(old_str, new_str)
                    
                    old_str2 = f'{func}("{name}"'
                    new_str2 = f'{func}("{final_map[name]}"'
                    new_content = new_content.replace(old_str2, new_str2)

            # Template replaces
            for name in pattern_template.findall(content):
                if name in ["admin:index", "login", "logout"]: continue
                if name in final_map:
                    old_str = f"{{% url '{name}'"
                    new_str = f"{{% url '{final_map[name]}'"
                    new_content = new_content.replace(old_str, new_str)
                    
                    old_str2 = f'{{% url "{name}"'
                    new_str2 = f'{{% url "{final_map[name]}"'
                    new_content = new_content.replace(old_str2, new_str2)
            
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Fixed substitutions in {path}")
                total_fixes += 1

print(f"Total de arquivos corrigidos: {total_fixes}")
