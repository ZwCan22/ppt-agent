from app.clients.dify import get_app_info

info = get_app_info()

print("应用名称：", info.get("name"))
print("应用类型：", info.get("mode"))