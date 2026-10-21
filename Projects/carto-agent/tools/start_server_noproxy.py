# -*- coding: utf-8 -*-
"""以无代理方式启动后端（沙箱代理 127.0.0.1:9 无效，清除后让 OSM 抓取可用）"""
import subprocess, os
backend = r"D:\AAA-Study\work\github\carto-agent\backend"
py = r"D:\python\py3.12.8\python.exe"
runtime = os.path.join(backend, "runtime")
os.makedirs(runtime, exist_ok=True)
out = open(os.path.join(runtime, "server_out.log"), "wb", buffering=0)
err = open(os.path.join(runtime, "server_err.log"), "wb", buffering=0)
CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | 0x00000200
env = dict(os.environ)
for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    env.pop(k, None)
env["PYTHONUNBUFFERED"] = "1"
p = subprocess.Popen(
    [py, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"],
    cwd=backend, stdout=out, stderr=err,
    creationflags=CREATE_NO_WINDOW | DETACHED, close_fds=True, env=env,
)
with open(os.path.join(runtime, "server.pid"), "w") as f:
    f.write(str(p.pid))
print("server pid:", p.pid)
