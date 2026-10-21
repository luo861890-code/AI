import urllib.request
import json, time

# 创建会话
req_body = json.dumps({"title": "测试地图"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8080/api/chat/sessions", data=req_body,
    headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req).read())
sid = resp.get("data", {}).get("session_id", "")
print(f"会话: {sid}")

# 非流式发送
msg_body = json.dumps({"message": "生成一份武汉市交通图"}).encode("utf-8")
req3 = urllib.request.Request(
    f"http://localhost:8080/api/chat/sessions/{sid}/messages",
    data=msg_body,
    headers={"Content-Type": "application/json"}
)
try:
    resp3 = json.loads(urllib.request.urlopen(req3, timeout=180).read())
    print(f"\nsuccess: {resp3.get('success')}")
    # Print the full response structure
    print(f"message: {resp3.get('message', '')[:100]}")
    data = resp3.get("data", {})
    if data:
        print(f"response: {str(data.get('response', ''))[:300]}")
        print(f"action: {data.get('action')}")
        map_data = data.get("map_data")
        if map_data:
            print(f"地图名: {map_data.get('name')}")
            print(f"图层数: {len(map_data.get('layers', []))}")
            for l in map_data.get('layers', [])[:5]:
                feats = l.get('features', l.get('data', {}).get('features',[]))
                nf = len(feats) if isinstance(feats, list) else (len(feats.get('features',[])) if isinstance(feats, dict) else 0)
                print(f"  {l.get('name','?')}: {l.get('type')} -> {nf} features")
except Exception as e:
    print(f"失败: {e}")
    import traceback
    traceback.print_exc()
