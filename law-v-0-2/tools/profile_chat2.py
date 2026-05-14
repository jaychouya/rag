import json, requests, time, sys

q = sys.argv[1] if len(sys.argv) > 1 else "噪音扰民"
mode = sys.argv[2] if len(sys.argv) > 2 else "fast"
t0 = time.time()
print(f"query: {q}  mode: {mode}", flush=True)
r = requests.post("http://localhost:8000/api/chat", json={"query": q, "mode": mode}, stream=True, timeout=600)
first_answer = False
event_count = 0
for chunk in r.iter_content(chunk_size=None):
    for line in chunk.decode("utf-8", errors="replace").split("\n"):
        if not line.startswith("data: "):
            continue
        event_count += 1
        try:
            d = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        elapsed = time.time() - t0
        if d["type"] == "progress":
            print(f"  [{elapsed:5.1f}s] progress", flush=True)
        elif d["type"] == "answer" and not first_answer:
            print(f"  [{elapsed:5.1f}s] FIRST ANSWER", flush=True)
            first_answer = True
        elif d["type"] == "error":
            print(f"  [{elapsed:5.1f}s] ERROR: {d['content'][:100]}", flush=True)
        elif d["type"] == "done":
            print(f"  [{elapsed:5.1f}s] DONE (total events: {event_count})", flush=True)
print(f"\ntotal: {time.time()-t0:.1f}s", flush=True)
