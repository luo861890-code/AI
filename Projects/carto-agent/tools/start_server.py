# -*- coding: utf-8 -*-
"""分离式启动 carto-agent 后端服务（无窗口、脱离会话，禁用reload以保证稳定）"""
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
env["PYTHONUNBUFFERED"] = "1"
p = subprocess.Popen(
    [py, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"],
    cwd=backend, stdout=out, stderr=err,
    creationflags=CREATE_NO_WINDOW | DETACHED, close_fds=True, env=env,
)
with open(os.path.join(runtime, "server.pid"), "w") as f:
    f.write(str(p.pid))
print("server pid:", p.pid)
