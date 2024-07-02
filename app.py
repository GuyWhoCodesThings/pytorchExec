import json
from flask import Flask, jsonify, request
import sys
from io import StringIO
import torch
from torch import nn
from torch.optim import SGD
import torch.nn.functional as F
import ast
import multiprocessing
from flask_cors import CORS, cross_origin

BANNED_WORDS = {"import", "from", "eval", "exec", "__import__", "open", "os", "sys"}

def isSafe(code):
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_WORDS:
                return False
        
        return True
    except SyntaxError:
        return False

def execute_code(text, result_dict):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    try:
        exec(compile(text, '<string>', 'exec'), {"nn": nn, "torch": torch, "F": F, "SGD": SGD}, {})
    except Exception as e:
        redirected_error.write(str(e))
    result_dict['out'] = redirected_output.getvalue()
    result_dict['error'] = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

def runCode(text):
    manager = multiprocessing.Manager()
    result_dict = manager.dict()
    p = multiprocessing.Process(target=execute_code, args=(text, result_dict))
    p.start()
    p.join(timeout=10)
    if p.is_alive():
        p.terminate()
        result_dict['error'] = 'timeout error'
    return dict(result_dict)

app = Flask(__name__)
CORS(app)

@app.route('/')
@cross_origin()
def home():
    return "Welcome! This API will let you execute python code with access to the pytorch packages"

@app.route('/dummy')
def test():
    code = "x=torch.rand(1000,20)\nm = nn.Linear(20,1)\nout=m(x)\nprint(out[:10])"
    if not isinstance(code, str):
        return jsonify({"error": "request data not a JSON string"}), 400
    if isSafe(code) == False:
        return jsonify({"error": "code contains unsafe ops or syntax error (ex. imports)."}), 400
    return runCode(code)

@app.route('/run', methods=["POST"])
@cross_origin()
def run():
    content = request.json
    code = content['code']
    if not isinstance(code, str):
        return jsonify({"error": "request data not a JSON string"}), 400
    if isSafe(code) == False:
        return jsonify({"error": "code contains unsafe ops or syntax error (ex. imports)."}), 400
    response = runCode(code)
    return jsonify({"error": response["error"], "stdout": response["out"]}), 200

if __name__ == '__main__':
    app.run()