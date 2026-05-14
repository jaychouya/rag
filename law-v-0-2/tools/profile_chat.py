import json, requests, time, sys

q = sys.argv[1] if len(sys.argv) > 1 else "信访条例第五条"
mode = sys.argv[2] if len(sys.argv) > 2 else "fast"
t0 = time.time()
r = requests.post("http://localhost:8000/api/chat", json={"query": q, "mode": mode}, stream=True, timeout=300)
first_answer = False
for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data: "):
        continue
    d = json.loads(line[6:])
    elapsed = time.time() - t0
    if d["type"] == "progress":
        txt = d["content"][:80]
        print(f"  [{elapsed:5.1f}s] progress: {txt}")
    elif d["type"] == "answer" and not first_answer:
        print(f"  [{elapsed:5.1f}s] === first answer chunk ===")
        first_answer = True
    elif d["type"] == "error":
        print(f"  [{elapsed:5.1f}s] ERROR: {d['content']}")
    elif d["type"] == "done":
        print(f"  [{elapsed:5.1f}s] done")
print(f"\ntotal: {time.time()-t0:.1f}s")
