from collections import deque
import executors.base as base
import threading
import requests
import typing
import time
import os


def _gen(f=input, *args, **kwargs):
    while (v := f(*args, **kwargs)) != None:
        yield v


# Converts constructs of "[[%s]]" or "([%s])" into an rsexec command.
def _parse_encap(api: base.api_base, encap, encap_i, level=0):
    if not len(encap):
        return encap
    do_parse = False
    trim = encap
    last_c = trim[-1]

    if last_c == "]" and encap_i == 0:
        trim = trim[1:-1]
        do_parse = True
        while len(trim) and trim[0] == "[" and trim[-1] == "]":
            trim = trim[1:-1]

    elif last_c in [")", "]"]:
        trim = trim[1:-1]
        while len(trim) and trim[0] == "[" and trim[-1] == "]":
            trim = trim[1:-1]
            do_parse = True

    # print(encap, do_parse)
    if do_parse:
        return parse_str(api, trim, level + 1)
    return encap


def _param_single(api: base.api_base, body: str, level=0) -> list[str]:
    encap_map = {
        "[": "]",
        "(": ")",
    }
    param_buf = ""
    encap_l = deque()

    i = -1
    for ch in body.split("--", 1)[0].strip():
        param_buf += ch
        i += 1

        # Executes if the last encap character's complement is found.
        if len(encap_l) and ch == encap_l[-1][1]:
            last_i, _ = encap_l.pop()
            encap = param_buf[last_i:]
            result = _parse_encap(api, encap, last_i, level=level)
            param_buf = param_buf[0:last_i] + result
            i += len(result) - len(encap)
            continue

        # Executes if an encapsulation character is found.
        if ch in encap_map:
            encap_l.append((i, encap_map[ch]))
            continue
    return param_buf


def _param_list(
    api: base.api_base, body: str, default="nil", level=0, max_split=-1
) -> list[str]:
    encap_map = {
        "'": "'",
        '"': '"',
        "[": "]",
        "(": ")",
        "{": "}",
    }
    params = []
    param_buf = ""
    escaped = False
    encap_l = deque()

    def finalise(buf):
        if buf == "":
            buf = default
        return buf

    i = -1
    for ch in body.split("--", 1)[0].strip():
        i += 1

        # Executes if backslash was previous character, irrespective of current's class.
        if escaped:
            param_buf += ch
            escaped = False
            continue

        # Adds backslash to buffer and triggers escape sequence.
        if ch == "\\":
            param_buf += ch
            escaped = True
            continue

        # Executes if the last encap character's complement is found.
        if len(encap_l) and ch == encap_l[-1][1]:
            param_buf += ch
            last_i, _ = encap_l.pop()
            encap = param_buf[last_i:]
            result = _parse_encap(api, encap, last_i, level=level)
            param_buf = param_buf[0:last_i] + result
            i += len(result) - len(encap)
            continue

        # Executes if an encapsulation character is found.
        if ch in encap_map:
            param_buf += ch
            encap_l.append((i, encap_map[ch]))
            continue

        # Executes if currently within encapsulation.
        if len(encap_l):
            param_buf += ch
            escaped = False
            continue

        # Executes if not encapsulated and is a space; adds result to param table and clears buffer.
        if max_split != 0 and ch.isspace():
            if param_buf != "":
                params.append(finalise(param_buf))
                param_buf = ""
                max_split -= 1
                i = -1
            continue

        else:
            param_buf += ch
            escaped = False

    params.append(finalise(param_buf))
    return params


def parse(api: base.api_base, input_gen=_gen(input), level=0):
    def func_head(arg_u):
        arg_t = f"local A={{{arg_u}}}"
        arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
        return f"{arg_t}\n{arg_n}"

    def output_call(s):
        return f"rsexec('save',{repr(api.OUTPUT_PATH_LUA)},{s},true)"

    line = next(input_gen).lstrip()
    if len(line) == 0:
        return
    head, body = (*line.split(" ", 1), "")[0:2]
    head_l = head.lower()

    # One-line snippet.
    if head_l in ["s", "snip", "snippet"]:
        arg_h = func_head("...")
        return _param_single(api, body, level=level)

    if head_l in ["f", "function"]:
        arg_h = func_head("...")
        f_body = _param_single(api, body, level=level)
        return f"(function(...)\n{arg_h}\n{f_body}\nend)"

    # Single-statement function; 'return' is prepended.
    elif head_l in ["l", "lambda"]:
        arg_h = func_head("...")
        f_body = _param_single(api, body, level=level)
        return f"(function(...)\n{arg_h}\nreturn {f_body}\nend)"

    # Treats each parameter as its own statement, outputs each to the console.
    elif head_l in ["o", "p", "output"]:
        o_nil = f"t=_G.EXEC_OUTPUT or t"
        o_loop = f"for _,v in next,t do\n{output_call('v')}\nend"
        o_reset = f"_G.EXEC_OUTPUT=nil"
        o_call = "\n".join(
            f"local t={{{s}}}\n{o_nil}\n{o_loop}\n{o_reset}"
            for s in _param_list(api, body, level=level)
        )
        return f"(function(...)\n{o_call}\nend)()"

    # Multi-line script.
    elif head_l in ["ml", "m", "multiline"]:
        lines = [body]
        while True:
            s_line = next(input_gen, "")
            lines.append(s_line)
            if len(s_line.strip()) == 0:
                break
        return _param_single(api, "\n".join(lines), level=level)

    # Lists Lua files in the workspace folder.
    elif head_l in ["ls", "list"]:
        for p in os.listdir("workspace"):
            if p.lower().endswith("lua"):
                print(f"- {p}")

    # Clears the console.
    elif head_l in ["cl", "cls", "clr"]:
        print("\033c", end="")

    elif head_l in ["r", "repeat"]:
        [var, rep_cmd, *_] = _param_list(api, body, level=level, max_split=1) + 2 * [""]
        append_block = f"T[I]={parse_str(api,rep_cmd, level=level)}"
        table_block = f"for I,V in next,({var})do\n{append_block}\nend"
        incr_block = f"for I=1,({var})do\n{append_block}\nend"
        return (
            f"(function()\nlocal T={{}}\n"
            + f"if typeof({var})=='table'then\n{table_block}\n"
            + f"else\n{incr_block}\nend\n"
            + f"return T\nend)()"
        )

    elif head_l in ["b", "batch"]:
        [var, script_body, *_] = _param_list(
            api, body, level=level, max_split=1
        ) + 2 * [""]
        return f"(function()\nfor I=1,({var})do\n{script_body}\nend\nend)"

    # Loads Lua(u) code from a URL.
    elif head_l in ["ls", "loadstring"]:
        [url, *args] = _param_list(api, body, level=level)
        arg_h = func_head(", ".join(args))
        script = requests.get(url)
        return f"(function()\n{arg_h}\n{script}\nend)()"

    elif head_l == ["e", "exit"]:
        exit()

    # Prints the returned output string of a command if we're on a top-level parse.
    join = "".join(f", {s}" for s in _param_list(api, body, level=level))
    if level == 0:
        o_loop = f"if _G.EXEC_OUTPUT then\nfor _,v in next,_G.EXEC_OUTPUT do\n{output_call('v')}\nend\nend"
        return f'rsexec("{head}"{join})\n{o_loop}'
    return f'rsexec("{head}"{join})'


def parse_str(api: base.api_base, s, level=0):
    return parse(api, (_ for _ in [s]), level=level)


# Shared resource pool to prevent file collisions.
INPUT_GEN = _gen(input)
PRINT_THREADS = {}

# https://github.com/dabeaz/generators/blob/master/examples/follow.py
def follow(fn):
    with open(fn, "r", encoding="utf-8") as o:
        while True:
            line: str = o.read().rstrip("\r\n")
            if not line:
                time.sleep(0)
                continue
            print(f"\033[93m{line}\033[00m")


def process(api: base.api_base, input_gen: typing.Iterator[str] = INPUT_GEN):
    path = api.OUTPUT_PATH_PY
    if path not in PRINT_THREADS:
        th = threading.Thread(target=follow, args=[path])
        PRINT_THREADS[path] = th
        th.daemon = True
        th.start()
    while True:
        script_body = parse(api, input_gen)
        if script_body:
            api.exec(script_body)
