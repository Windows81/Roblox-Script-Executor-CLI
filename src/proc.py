import executors.base as base
from collections import deque
from io import BufferedReader
import requests
import typing
import time
import os


def _gen(f=input, *args, **kwargs):
    while (v := f(*args, **kwargs)) != None:
        yield v


# Shared resource pool to prevent file collisions.
INPUT_GEN = _gen(input, "\x1b[00m> \033[93m")
FILE_THREADS: dict[str, BufferedReader] = {}


def _follow_output(o: BufferedReader):
    data = bytes()
    while True:
        data = o.read()
        if not data:
            time.sleep(0)
            continue
        break

    tries = 1e5
    done = False
    while tries > 0:
        if data:
            if data[-1] == 0:
                splice = data[:-1]
                tries = 1e3
            else:
                splice = data
                tries = 2e5
            if splice:
                ps = splice.decode("utf-8")
                print(ps, end="")
                done = True
        else:
            tries -= 1
        time.sleep(0)
        data = o.read()
    print(f"", end="\n" if done else "")
    return done


# https://github.com/dabeaz/generators/blob/master/examples/follow.py
def _print_to_end(o: BufferedReader):
    data = bytes()
    done = False
    while True:
        data = o.read()
        if not data:
            break
        done = True
        ps = data.decode("utf-8")
        print(ps, end="")
    print("", end="\n" if done else "")
    return done


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
    api: base.api_base, body: str, default="nil", level=0, max_split=-1, min_params=0
) -> list[str]:
    encap_map = {
        "'": "'",
        '"': '"',
        "[": "]",
        "(": ")",
        "{": "}",
    }
    params = []
    # raw_ps = []
    param_buf = ""
    # raw_p_buf = ""
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
            # raw_p_buf += ch
            escaped = False
            continue

        # Adds backslash to buffer and triggers escape sequence.
        if ch == "\\":
            param_buf += ch
            # raw_p_buf += ch
            escaped = True
            continue

        # Executes if the last encap character's complement is found.
        if len(encap_l) and ch == encap_l[-1][1]:
            param_buf += ch
            # raw_p_buf += ch
            last_i, _ = encap_l.pop()
            encap = param_buf[last_i:]
            result = _parse_encap(api, encap, last_i, level=level)
            param_buf = param_buf[0:last_i] + result
            i += len(result) - len(encap)
            continue

        # Executes if an encapsulation character is found.
        if ch in encap_map:
            param_buf += ch
            # raw_p_buf += ch
            encap_l.append((i, encap_map[ch]))
            continue

        # Executes if currently within encapsulation.
        if len(encap_l):
            param_buf += ch
            # raw_p_buf += ch
            escaped = False
            continue

        # Executes if not encapsulated and is a space; adds result to param table and clears buffer.
        if max_split != 0 and ch.isspace():
            if param_buf != "":
                # raw_ps.append(raw_p_buf)
                params.append(finalise(param_buf))
                param_buf = ""
                # raw_p_buf = ""
                max_split -= 1
                i = -1
            continue

        else:
            param_buf += ch
            # raw_p_buf += ch
            escaped = False

    params.append(finalise(param_buf))
    params.extend((min_params - len(params)) * [default])
    # raw_ps.append(raw_p_buf)
    # raw_ps.extend((min_params - len(raw_ps)) * [default])
    return params  # , raw_ps


def parse(api: base.api_base, input_gen=INPUT_GEN, level=0) -> str | None:
    def func_head(arg_u):
        arg_t = f"local A={{{arg_u}}}"
        arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
        return f"{arg_t}\n{arg_n}"

    line = ""
    while True:
        n = next(input_gen, None)
        if not n:
            return
        line = n.lstrip()
        if len(line) == 0:
            continue

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
        elif head_l in ["o", "output"]:
            param_o = []
            # pattern = re.compile("^\[\[.+\]\]$")
            for s in _param_list(api, body, level=level):
                # is_single = pattern.match(r)
                # o_nil = f"t=_E.OUTPUT or t" if is_single else ""
                o_call = api.output_call("v")
                o_loop = f"for _,v in next,t do\n{o_call}\nend"
                o_reset = f"_E.OUTPUT=nil"  # if level == 0 else ""
                param_o.append(f"local t={{{s}}}\n{o_loop}\n{o_reset}")
            o_body = "\n".join(param_o)
            return f"(function(...)\n{o_body}\nend)()"

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
            for pos in os.listdir("workspace"):
                if pos.lower().endswith("lua"):
                    print(f"- {pos}")
            continue

        # Clears the console.
        elif head_l in ["cl", "cls", "clr"]:
            print("\033c", end="")
            continue

        elif head_l in ["r", "repeat"]:
            [var, cmd] = _param_list(api, body, level=level, max_split=1, min_params=2)
            append_block = f"T[I]={parse_str(api,cmd, level=level)}"
            table_block = f"for I,V in next,({var})do\n{append_block}\nend"
            incr_block = f"for I=1,({var})do\n{append_block}\nend"
            return (
                f"(function()\nlocal T={{}}\n"
                + f"if typeof({var})=='table'then\n{table_block}\n"
                + f"else\n{incr_block}\nend\n"
                + f"return T\nend)()"
            )

        elif head_l in ["b", "batch"]:
            [var, sb] = _param_list(api, body, level=level, max_split=1, min_params=2)
            return f"(function()\nfor I=1,({var})do\n{sb}\nend\nend)"

        # Loads Lua(u) code from a URL.
        elif head_l in ["ls", "loadstring"]:
            [url, *args] = _param_list(api, body, level=level)
            arg_h = func_head(", ".join(args))
            script = requests.get(url)
            return f"(function()\n{arg_h}\n{script}\nend)()"

        elif head_l in ["dump"]:
            try:
                [name, sub] = _param_list(
                    api, body, level=level, max_split=1, min_params=2, default=""
                )
                print("\x1b[00m", end="")
                path = os.path.join(api.WORKSPACE_DIR, f"_{name}.dat")
                opened = name in FILE_THREADS
                if sub.lower() == "reset":
                    if opened:
                        pos = FILE_THREADS[name].tell()
                        FILE_THREADS[name].seek(0)
                        print(f'Reset "{path}" from byte {hex(pos)}.')
                    else:
                        FILE_THREADS[name] = open(path, "rb")
                        print(f'Opened "{path}".')
                    continue

                elif not opened:
                    FILE_THREADS[name] = open(path, "rb")
                _print_to_end(FILE_THREADS[name])
            except FileNotFoundError:
                print(f'\x1b[91mUnable to find "{path}".')
            continue

        elif head_l == ["e", "exit"]:
            return None

        # Prints the returned output string of a command if we're on a top-level parse.
        pl = _param_list(api, body, level=level)
        join = "".join(f", {s}" for s in pl)
        if level == 0:
            o_call = api.output_call("v")
            o_loop = f"if t then\nfor _,v in next,t do\nprint(v)\n{o_call}\nend\nend"
            return f'local r={{_E("{head}"{join})}}\nlocal t=_E.OUTPUT or r\n{o_loop}'
        return f'_E("{head}"{join})'


def parse_str(api: base.api_base, s, level=0):
    return parse(api, (_ for _ in [s]), level=level)


def process(api: base.api_base, input_gen: typing.Iterator[str] = INPUT_GEN):
    path = os.path.join(api.WORKSPACE_DIR, api.OUTPUT_DUMP)
    try:
        with open(path, "rb") as o:
            while True:
                script_body = parse(api, input_gen)
                if not script_body:
                    break
                out_n = api.output_call('"\\0"')
                out_e = api.output_call('"\\n\x1b[91m"..e.."\x1b[00m"')
                err_b = f"if not s then\n{out_e}\nend"
                msg_e = "Syntax error; perhaps check the devconsole."
                err_s = api.output_call(f'"\x1b[91m{msg_e}\x1b[00m\\0"')
                pcall = f"local s,e=pcall(function()\n{script_body};end)"
                for l in [
                    f"_E.RUN=true\n{pcall}\n{err_b}\ntask.wait(1/8)\n{out_n}\n_E.RUN=false",
                    f"task.wait(1/64)\nif not _E.RUN then\n{err_s}\nend",
                ]:
                    api.exec(l)
                print(f"\x1b[00m", end="")
                _follow_output(o)

    except KeyboardInterrupt:
        pass
    finally:
        print("\033[00m", end="")
