from dataclasses import dataclass
from enum import Enum
import executors.base as base
from collections import deque
from io import BufferedReader
import requests
import typing
import time
import os


class ParseCode(Enum):
    EXIT = 0
    SYNC = 1
    ASYNC = 2
    RAW = 3
    RESTART = 4


@dataclass
class ParseResult:
    string: str
    code: ParseCode


def _gen(f=input, *args, **kwargs):
    while (v := f(*args, **kwargs)) != None:
        yield v


# Shared resource pool to prevent file collisions.
INPUT_GEN = _gen(input, "\033[93m")
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
    processed = False
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
                processed = True
        else:
            tries -= 1
        time.sleep(0)
        data = o.read()
    return processed


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


def _param_single(api: base.api_base, body: str, level=0):
    encap_map = {
        "[": "]",
        "(": ")",
    }
    param_buf: str = ""
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
):
    encap_map = {
        "'": "'",
        '"': '"',
        "[": "]",
        "(": ")",
        "{": "}",
    }
    params: list[str] = []
    # raw_ps: list[str] = []
    param_buf: str = ""
    # raw_p_buf: str = ""
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


def parse(api: base.api_base, input_gen=INPUT_GEN, level=0):
    def func_head(arg_u):
        if not arg_u:
            arg_u = "nil"
        arg_t = f"local A={{{arg_u}}}"
        arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
        return f"{arg_t}\n{arg_n}"

    line = ""
    if not level:
        print(f"\x1b[00m> ", end="")
    n = next(input_gen, None)
    if not n:
        return ParseResult("", ParseCode.RAW)
    line = n.lstrip()
    if len(line) == 0:
        return ParseResult("", ParseCode.RAW)

    head, body = (*line.split(" ", 1), "")[0:2]
    head_l = head.lower()

    o_call = api.output_call("v")
    sep_c = api.output_call("'\x1b[00m; '")
    o_sep = f"if i>1 then\n{sep_c}\nend"
    o_loop = f"if t then\nfor i,v in next,t do\n{o_sep}\n{o_call}\nend\nend"

    # One-line snippet.
    if head_l in ["s", "snip", "snippet"]:
        arg_h = func_head("...")
        return ParseResult(_param_single(api, body, level=level), ParseCode.SYNC)

    elif head_l in ["f", "func", "function"]:
        arg_h = func_head("...")
        f_body = _param_single(api, body, level=level)
        f_str = f"(function(...)\n{arg_h}\n{f_body}\nend)"
        return ParseResult(f_str, ParseCode.RAW)

    # Single-statement function; 'return' is prepended.
    elif head_l in ["l", "lambda"]:
        arg_h = func_head("...")
        f_body = _param_single(api, body, level=level)
        f_str = f"(function(...)\n{arg_h}\nreturn {f_body}\nend)"
        return ParseResult(f_str, ParseCode.RAW)

    # Treats each parameter as its own statement, outputs each to the console.
    elif head_l in ["o", "output"]:
        param_o = []
        for alias in _param_list(api, body, level=level):
            param_o.append(f"{{{alias}}},")
            o_reset = f"_E.OUTPUT=nil"
        o_body = "\n".join(param_o)
        if level:
            o_nl = api.output_call('"\\n"')
        else:
            o_nl = ""
        return ParseResult(
            f"(function(...)\nfor i,t in next,{{{o_body}}}do\n{o_sep}\n{o_loop}\n{o_nl}\n{o_reset}\nend\nend)()",
            ParseCode.SYNC,
        )

    # Multi-line script.
    elif head_l in ["ml", "m", "multiline"]:
        lines = [body]
        while True:
            s_line = next(input_gen, "")
            lines.append(s_line)
            if len(s_line.strip()) == 0:
                break
        return ParseResult(
            _param_single(api, "\n".join(lines), level=level), ParseCode.SYNC
        )

    # Lists Lua files in the workspace folder.
    elif head_l in ["list"]:
        for pos in os.listdir("workspace"):
            if pos.lower().endswith("lua"):
                print(f"- {pos}")
        return ParseResult("", ParseCode.RAW)

    # Clears the console.
    elif head_l in ["cl", "cls", "clr"]:
        print("\033c", end="")
        return ParseResult("", ParseCode.RAW)

    elif head_l in ["repeat"]:
        [var, cmd] = _param_list(api, body, level=level, max_split=1, min_params=2)
        append_block = f"T[I]={parse_str(api,cmd, level=level)}"
        table_block = f"for I,V in next,({var})do\n{append_block}\nend"
        incr_block = f"for I=1,({var})do\n{append_block}\nend"
        return ParseResult(
            f"(function()\nlocal T={{}}\n"
            + f"if typeof({var})=='table'then\n{table_block}\n"
            + f"else\n{incr_block}\nend\n"
            + f"return T\nend)()",
            ParseCode.SYNC,
        )

    elif head_l in ["b", "batch"]:
        [var, sb] = _param_list(api, body, level=level, max_split=1, min_params=2)
        return ParseResult(
            f"(function()\nfor I=1,({var})do\n{sb}\nend\nend)", ParseCode.SYNC
        )

    # Loads Lua(u) code from a URL.
    elif head_l in ["ls", "loadstring"]:
        [url, *args] = _param_list(api, body, level=level)
        arg_h = func_head(", ".join(args))
        try:
            script = requests.get(url)
            return ParseResult(
                f"(function()\n{arg_h}\n{script.text}\nend)()", ParseCode.ASYNC
            )
        except requests.exceptions.RequestException as e:
            print(f"\x1b[91m{e.strerror}")
            return ParseResult("", ParseCode.RAW)

    elif head_l in ["man"]:
        alias = _param_single(api, body, level=level)
        if level:
            return ParseResult(f'_E("man",{repr(alias)})', ParseCode.SYNC)

        o_call = api.output_call(
            f"'\\n\x1b[93m'..gsp:upper()"
            + "..':\\n\x1b[94m'..man"
            + ":gsub('\\r\\n','\\n')"
            + ":gsub('%[(%d+)%] %- ([^\\n]+)\\n([^%[]+)', '\x1b[91m%1) \x1b[92m%2\x1b[90m\\n%3')"
            + ":gsub('\\n\\t','\\n    ')"
            + f'.."\\n\x1b[00m"'
        )
        gsp_e = api.output_call(f'"\x1b[91mAlias does not exist.\x1b[00m\\0"')
        gsp_s = (
            f"local gsp=_E.GSP({repr(alias)})\n"
            + f"if not gsp then\n{gsp_e}\nreturn\nend"
        )
        man_e = api.output_call(
            f'"\x1b[91mAlias does not have help metatext.\x1b[00m\\0"'
        )
        man_s = (
            f"local man=_E('man',{repr(alias)})\n"
            + f"if not man then\n{man_e}\nreturn\nend"
        )
        return ParseResult(
            f"{gsp_s}\n{man_s}\n{o_call}",
            ParseCode.SYNC,
        )

    elif head_l in ["dump"] and not level:
        try:
            [name, sub] = _param_list(
                api, body, level=level, max_split=1, min_params=2, default=""
            )
            print("\x1b[00m", end="")
            path = os.path.join(api._workspace_dir, f"_{name}.dat")
            opened = name in FILE_THREADS
            if sub.lower() == "reset":
                if opened:
                    pos = FILE_THREADS[name].tell()
                    FILE_THREADS[name].seek(0)
                    print(f'Reset "{path}" from byte {hex(pos)}.')
                else:
                    FILE_THREADS[name] = open(path, "rb")
                    print(f'Opened "{path}".')
                return ParseResult("", ParseCode.RAW)

            elif not opened:
                FILE_THREADS[name] = open(path, "rb")
            _print_to_end(FILE_THREADS[name])
        except FileNotFoundError:
            print(f'\x1b[91mUnable to find "{path}".')
        return ParseResult("", ParseCode.RAW)

    elif head_l in ["r", "reset", "restart"]:
        return ParseResult(None, ParseCode.RESTART)

    elif head_l == ["e", "exit"]:
        return ParseResult(None, ParseCode.EXIT)

    pl = _param_list(api, body, level=level)
    join = "".join(f", {s}" for s in pl)
    if level:
        return ParseResult(f'_E("{head}"{join})', ParseCode.SYNC)

    # Prints the returned output string of a command if we're on a top-level parse.
    return ParseResult(
        f'local r={{_E("{head}"{join})}}\nlocal t=_E.OUTPUT or r\n{o_loop}',
        ParseCode.SYNC,
    )


def parse_str(api: base.api_base, s, level=0):
    return parse(api, (_ for _ in [s]), level=level).string


def process(api: base.api_base, input_gen: typing.Iterator[str] = INPUT_GEN):
    try:
        while True:
            result = parse(api, input_gen)
            out_n = api.output_call('"\\0"')
            out_e = api.output_call('"\x1b[91m"..e.."\x1b[00m"')
            err_b = f"if not s then\n{out_e}\nend"
            msg_e = "Syntax error; perhaps check the devconsole."
            err_s = api.output_call(f'"\x1b[91m{msg_e}\x1b[00m\\0"')
            pcall = f"local s,e=pcall(function()\n{result.string};end)"
            var = f"_E.RUN{str(time.time()).replace('.','')}"

            if result.code == ParseCode.SYNC:
                script_lines = [
                    f"local c=7\nrepeat c=c-1\ntask.wait(0)\nif {var} then\nreturn\nend\nuntil c==0\n{err_s}",
                    f"{var}=true\n{pcall}\n{err_b}\ntask.wait(0.2)\n{out_n}\n{var}=false",
                ]
            elif result.code == ParseCode.ASYNC:
                script_lines = [f"{pcall}\n{err_b}\n{out_n}"]
            elif result.code == ParseCode.RAW:
                if not result:
                    continue
                script_lines = [result]
            elif result.code == ParseCode.EXIT:
                break
            elif result.code == ParseCode.RESTART:
                api.restart()
                continue

            for l in script_lines:
                api.exec(l)

            print(f"\x1b[00m", end="")
            try:
                anything = api.follow_output()
                print(f"", end="\n" if anything else "")
            except KeyboardInterrupt:
                print(
                    "\x1b[91mProcess is still running; future output may be garbled.",
                    end="\n",
                )

    except KeyboardInterrupt:
        pass
    finally:
        print("\033[00m", end="")
