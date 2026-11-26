import os, sys, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
import render

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(root, "out"), exist_ok=True)
only = sys.argv[1:]
for i in range(1, 37):
    name = "case-%02d" % i
    if only and name not in only:
        continue
    t = time.time()
    try:
        notes = render.render_case(os.path.join(root, "cases", name), os.path.join(root, "out", name + "-1.png"))
        print(name, "ok %.1fs" % (time.time() - t), notes)
    except Exception:
        print(name, "FAILED")
        traceback.print_exc()
