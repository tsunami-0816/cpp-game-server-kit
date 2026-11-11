import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import sys, os.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
import game_pb2
r = game_pb2.LoginReq()
r.username = "user1"
r.password = "123456"
body = r.SerializeToString()
r2 = game_pb2.LoginReq()
r2.ParseFromString(body)
print("OK len=", len(body), "user=", r2.username)
