from dataclasses import dataclass
from enum import Enum
import executors.base as base
from collections import deque
from io import BufferedReader
import requests
import typing
import time
import os


class ParseStatus(Enum):
    EXIT = -1
    RESTART = 0
    RAW = 1
    SYNC = 2
    ASYNC = 3
    CLEAR = 5


@dataclass
class ParseResult:
    status: ParseStatus
    script: str = ""


def _gen(f=input, *args, **kwargs):
    while (v := f(*args, **kwargs)) != None:
        yield v


# Shared resource pool to prevent file collisions.
INPUT_GEN = _gen(input, "\033[93m")
FILE_THREADS: dict[str, BufferedReader] = {}


def _func_head(arg_u):
    if not arg_u:
        arg_u = "nil"
    arg_t = f"local A={{{arg_u}}}"
    arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
    return f"{arg_t}\n{arg_n}"


def cmd_snippet(api: base.api_base, body: str, level=0, **_kwa):
    s_body = _param_single(api, body, level=level, **_kwa)
    return ParseResult(ParseStatus.SYNC, s_body)


def cmd_function(api: base.api_base, body: str, level=0, **_kwa):
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level, **_kwa)
    f_str = f"(function(...)\n{arg_h}\n{f_body}\nend)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_lambda(api: base.api_base, body: str, level=0, **_kwa):
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level, **_kwa)
    f_str = f"(function(...)\n{arg_h}\nreturn {f_body}\nend)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_output(api: base.api_base, body: str, level=0, **_kwa):
    o_nl = api.output_call('"\\n"') if level else ""
    o_call = api.output_call("v")
    sep_c = api.output_call("'\x1b[00m; '")

    param_l = _param_list(api, body, level=level, **_kwa)
    o_body = "\n".join(f"{{{alias}}}," for alias in param_l)

    o_sep = f"if i>1 then\n{sep_c}\nend"
    o_loop = f"if t then\nfor i,v in next,t do\n{o_sep}\n{o_call}\nend\nend"
    o_reset = f"_E.OUTPUT=nil"
    s_body = f"(function(...)\nfor i,t in next,{{{o_body}}}do\n{o_sep}\n{o_loop}\n{o_nl}\n{o_reset}\nend\nend)()"
    return ParseResult(ParseStatus.SYNC, s_body)


def cmd_multiline(api: base.api_base, input_gen, body: str, level=0, **_kwa):
    lines = [body]
    while True:
        s_line = next(input_gen, "")
        lines.append(s_line)
        if len(s_line.strip()) == 0:
            break
    return ParseResult(
        ParseStatus.SYNC,
        _param_single(api, "\n".join(lines), level=level, **_kwa),
    )


def cmd_list():
    for pos in os.listdir("workspace"):
        if pos.lower().endswith("lua"):
            print(f"- {pos}")
    return ParseResult(ParseStatus.RAW)


def cmd_repeat(api: base.api_base, body: str, level=0, **_kwa):
    [var, cmd] = _param_list(api, body, level=level, max_split=1, min_params=2, **_kwa)
    append_block = f"T[I]={parse_str(api,cmd, level=level, **_kwa)}"
    table_block = f"for I,V in next,({var})do\n{append_block}\nend"
    incr_block = f"for I=1,({var})do\n{append_block}\nend"
    return ParseResult(
        ParseStatus.SYNC,
        f"(function()\nlocal T={{}}\n"
        + f"if typeof({var})=='table'then\n{table_block}\n"
        + f"else\n{incr_block}\nend\n"
        + f"return T\nend)()",
    )


def cmd_batch(api: base.api_base, body: str, level=0, **_kwa):
    [var, sb] = _param_list(api, body, level=level, max_split=1, min_params=2, **_kwa)
    b_func = f"(function()\nfor I=1,({var})do\n{sb}\nend\nend)"
    return ParseResult(ParseStatus.SYNC, b_func)


def cmd_loadstring(api: base.api_base, body: str, level=0, **_kwa):
    [url, *args] = _param_list(api, body, level=level, **_kwa)
    arg_h = _func_head(", ".join(args))
    try:
        script = requests.get(url)
        body = f"(function()\n{arg_h}\n{script.text}\nend)()"
        return ParseResult(ParseStatus.ASYNC, body)

    except requests.exceptions.RequestException as e:
        print(f"\x1b[91m{e.strerror}")
        return ParseResult(ParseStatus.RAW)


def cmd_man(api: base.api_base, body: str, level=0, **_kwa):
    alias = _param_single(api, body, level=level, **_kwa)
    if level:
        return ParseResult(ParseStatus.SYNC, f'_E.EXEC("man",{repr(alias)})')

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
        f"local gsp=_E.GSP({repr(alias)})\n" + f"if not gsp then\n{gsp_e}\nreturn\nend"
    )
    man_e = api.output_call(f'"\x1b[91mAlias does not have help metatext.\x1b[00m\\0"')
    man_s = (
        f"local man=_E.EXEC('man',{repr(alias)})\n"
        + f"if not man then\n{man_e}\nreturn\nend"
    )
    return ParseResult(
        ParseStatus.SYNC,
        f"{gsp_s}\n{man_s}\n{o_call}",
    )


def cmd_dump(api: base.api_base, body: str, level=0, print=print, **_kwa):
    try:
        [name, sub] = _param_list(
            api,
            body,
            level=level,
            max_split=1,
            min_params=2,
            default="",
            **_kwa,
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
            return ParseResult(ParseStatus.RAW)

        elif not opened:
            FILE_THREADS[name] = open(path, "rb")
        _print_to_end(FILE_THREADS[name])
    except FileNotFoundError:
        print(f'\x1b[91mUnable to find "{path}".')
    return ParseResult(ParseStatus.RAW, print)


def cmd_generic(api: base.api_base, head: str, body: str, level=0, **_kwa):
    o_call = api.output_call("v")
    sep_c = api.output_call("'\x1b[00m; '")
    o_sep = f"if i>1 then\n{sep_c}\nend"
    o_loop = f"if t then\nfor i,v in next,t do\n{o_sep}\n{o_call}\nend\nend"

    pl = _param_list(api, body, level=level)
    join = "".join(f", {s}" for s in pl)
    if level:
        return ParseResult(ParseStatus.SYNC, f'_E.EXEC("{head}"{join})')

    # Prints the returned output script of a command if we're on a top-level parse.
    body = f'local r={{_E.EXEC("{head}"{join})}}\nlocal t=_E.OUTPUT or r\n{o_loop}'
    return ParseResult(ParseStatus.SYNC, body)


# https://github.com/dabeaz/generators/blob/master/examples/follow.py
def _print_to_end(o: BufferedReader, print=print):
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
def _parse_encap(api: base.api_base, encap, encap_i, level=0, **_kwa):
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
        return parse_str(api, trim, level=level + 1, **_kwa)
    return encap


def _param_single(api: base.api_base, body: str, level=0, **_kwa):
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
            result = _parse_encap(api, encap, last_i, level=level, **_kwa)
            param_buf = param_buf[0:last_i] + result
            i += len(result) - len(encap)
            continue

        # Executes if an encapsulation character is found.
        if ch in encap_map:
            encap_l.append((i, encap_map[ch]))
            continue
    return param_buf


def _param_list(
    api: base.api_base,
    body: str,
    default="nil",
    level=0,
    max_split=-1,
    min_params=0,
    *_a,
    **_kwa,
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
            result = _parse_encap(api, encap, last_i, level=level, **_kwa)
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


def _parse_rec(api: base.api_base, input_gen=INPUT_GEN, level=0, print=print, **_kwa):
    line = ""
    first_l = next(input_gen, None)
    if not first_l:
        return ParseResult(ParseStatus.RAW)
    line = first_l.lstrip()
    if len(line) == 0:
        return ParseResult(ParseStatus.RAW)

    head, body = (*line.split(" ", 1), "")[0:2]
    head_l = head.lower()
    kwargs = {
        "api": api,
        "head": head,
        "body": body,
        "input_gen": input_gen,
        "level": level,
        "print": print,
        **_kwa,
    }

    # One-line snippet.
    if head_l in ["s", "snip", "snippet"]:
        return cmd_snippet(**kwargs)

    elif head_l in ["f", "func", "function"]:
        return cmd_function(**kwargs)

    # Single-statement function; 'return' is prepended.
    elif head_l in ["l", "lambda"]:
        return cmd_lambda(**kwargs)

    # Treats each parameter as its own statement, outputs each to the console.
    elif head_l in ["o", "output"]:
        return cmd_output(**kwargs)

    # Multi-line script.
    elif head_l in ["ml", "m", "multiline"]:
        return cmd_multiline(**kwargs)

    # Lists Lua files in the workspace folder.
    elif head_l in ["list"]:
        return cmd_list(**kwargs)

    elif head_l in ["repeat"]:
        return cmd_repeat(**kwargs)

    elif head_l in ["b", "batch"]:
        return cmd_batch(**kwargs)

    # Loads Lua(u) code from a URL.
    elif head_l in ["ls", "loadstring"]:
        return cmd_loadstring(**kwargs)

    # Generates help page for the given command alias.
    elif head_l in ["man"]:
        return cmd_man(**kwargs)

    elif head_l in ["dump"] and not level:
        return cmd_dump(**kwargs)

    elif head_l in ["r", "reset", "restart"]:
        return ParseResult(ParseStatus.RESTART)

    # Clears the console.
    elif head_l in ["cl", "cls", "clr"]:
        return ParseResult(ParseStatus.CLEAR)

    elif head_l == ["e", "exit"]:
        return ParseResult(ParseStatus.EXIT)

    else:
        return cmd_generic(**kwargs)


def parse_str(api: base.api_base, string: str, **_kwa):
    res: ParseResult = _parse_rec(api, (_ for _ in [string]), **_kwa)
    return res.script


def parse(api: base.api_base, input_gen=INPUT_GEN, print=print):
    return _parse_rec(api, input_gen, level=0, print=print)


def process(api: base.api_base, input_gen: typing.Iterator[str] = INPUT_GEN):
    try:
        while True:
            script_lines = None
            result = parse(api, input_gen, print)
            out_n = api.output_call('"\\0"')
            out_e = api.output_call('"\x1b[91m"..e.."\x1b[00m"')
            err_b = f"if not s then\n{out_e}\nend"
            msg_e = "Syntax error; perhaps check the devconsole."
            err_s = api.output_call(f'"\x1b[91m{msg_e}\x1b[00m\\0"')
            pcall = f"local s,e=pcall(function()\n{result.script};end)"
            var = f"_E.RUN{str(time.time()).replace('.','')}"

            if result.status == ParseStatus.SYNC:
                script_lines = [
                    f"local c=7\nrepeat c=c-1\ntask.wait(0)\nif {var} then\nreturn\nend\nuntil c==0\n{err_s}",
                    f"{var}=true\n{pcall}\n{err_b}\ntask.wait(0.2)\n{out_n}\n{var}=false",
                ]

            elif result.status == ParseStatus.ASYNC:
                script_lines = [f"{pcall}\n{err_b}\n{out_n}"]

            elif result.status == ParseStatus.RAW and result.script:
                script_lines = [result.script]

            elif result.status == ParseStatus.RESTART:
                api.restart()

            elif result.status == ParseStatus.CLEAR:
                print("\033c", end="")

            elif result.status == ParseStatus.EXIT:
                break

            if not script_lines:
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
    except EOFError:
        pass
    finally:
        print("\033[00m", end="")
