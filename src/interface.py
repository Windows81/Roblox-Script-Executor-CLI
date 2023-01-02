from dataclasses import dataclass
import executors.base as base
from collections import deque
from io import BufferedReader
import executors.dump as dump
from enum import Enum
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


def _gen(f=input, *args, **kwargs) -> typing.Generator[str, None, None]:
    while (v := f(*args, **kwargs)) != None:
        yield v


# Shared resource pool to prevent file collisions.
INPUT_GEN = _gen(input)
FILE_THREADS: dict[str, BufferedReader] = {}


def _func_head(arg_u) -> str:
    if not arg_u:
        arg_u = "nil"
    arg_t = f"local A={{{arg_u}}}"
    arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
    return f"{arg_t}\n{arg_n}"


def cmd_snippet(api: base.api_base, body: str, level=0) -> ParseResult:
    s_body = _param_single(api, body, level=level)
    return ParseResult(ParseStatus.SYNC, s_body)


def cmd_function(api: base.api_base, body: str, level=0) -> ParseResult:
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level)
    f_str = f"(function(...)\n{arg_h}\n{f_body}\nend)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_lambda(api: base.api_base, body: str, level=0) -> ParseResult:
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level)
    f_str = f"(function(...)\n{arg_h}\nreturn {f_body}\nend)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_output(api: base.api_base, body: str, level=0) -> ParseResult:
    o_nl = api.output_call('"\\n"') if level else ""
    o_call = api.output_call("v")
    sep_c = api.output_call("'\x1b[00m; '")

    param_l = _param_list(api, body, level=level)
    o_body = "\n".join(f"{{{alias}}}," for alias in param_l)

    o_sep = f"if i>1 then\n{sep_c}\nend"
    o_loop = f"if t then\nfor i,v in next,t do\n{o_sep}\n{o_call}\nend\nend"
    o_reset = f"_E.OUTPUT=nil"
    s_body = f"(function(...)\nfor i,t in next,{{{o_body}}}do\n{o_sep}\n{o_loop}\n{o_nl}\n{o_reset}\nend\nend)()"
    return ParseResult(ParseStatus.SYNC, s_body)


def cmd_multiline(api: base.api_base, input_gen, body: str, level=0) -> ParseResult:
    lines = [body]
    while True:
        s_line = next(input_gen, "")
        lines.append(s_line)
        if len(s_line.strip()) == 0:
            break
    return ParseResult(
        ParseStatus.SYNC,
        _param_single(api, "\n".join(lines), level=level),
    )


def cmd_list() -> ParseResult:
    for pos in os.listdir("workspace"):
        if pos.lower().endswith("lua"):
            print(f"- {pos}")
    return ParseResult(ParseStatus.RAW)


def cmd_repeat(api: base.api_base, body: str, level=0) -> ParseResult:
    [var, cmd] = _param_list(api, body, level=level,
                             max_split=1, min_params=2)

    append_block = f"T[I]={parse_str(api, cmd, level=level)}"
    table_block = f"for I,V in next,({var})do\n{append_block}\nend"
    incr_block = f"for I=1,({var})do\n{append_block}\nend"
    return ParseResult(
        ParseStatus.SYNC,
        f"(function()\nlocal T={{}}\n"
        + f"if typeof({var})=='table'then\n{table_block}\n"
        + f"else\n{incr_block}\nend\n"
        + f"return T\nend)()",
    )


def cmd_batch(api: base.api_base, body: str, level=0) -> ParseResult:
    [var, sb] = _param_list(api, body, level=level,
                            max_split=1, min_params=2)

    b_func = f"(function()\nfor I=1,({var})do\n{sb}\nend\nend)"
    return ParseResult(ParseStatus.SYNC, b_func)


def cmd_loadstring(api: base.api_base, body: str, level=0) -> ParseResult:
    [url, *args] = _param_list(api, body, level=level)
    arg_h = _func_head(", ".join(args))
    try:
        script = requests.get(url)
        body = f"(function()\n{arg_h}\n{script.text}\nend)()"
        return ParseResult(ParseStatus.ASYNC, body)

    except requests.exceptions.RequestException as e:
        print(f"\x1b[91m{e.strerror}")
        return ParseResult(ParseStatus.RAW)


def cmd_man(api: base.api_base, body: str, level=0) -> ParseResult:
    alias = _param_single(api, body, level=level)
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
        f"local gsp=_E.GSP({repr(alias)})\n" +
        f"if not gsp then\n{gsp_e}\nreturn\nend"
    )
    man_e = api.output_call(
        f'"\x1b[91mAlias does not have help metatext.\x1b[00m\\0"')
    man_s = (
        f"local man=_E.EXEC('man',{repr(alias)})\n"
        + f"if not man then\n{man_e}\nreturn\nend"
    )
    return ParseResult(
        ParseStatus.SYNC,
        f"{gsp_s}\n{man_s}\n{o_call}",
    )


def cmd_dump(api: base.api_base, body: str, level=0, print=print) -> ParseResult:
    [name, sub] = _param_list(
        api,
        body,
        level=level,
        max_split=1,
        min_params=2,
        default="",
    )
    try:
        print("\x1b[00m", end="")
        if sub.lower() == "reset":
            pos = api.dump_reset(name)
            print(f'Reset "{name}" from byte {hex(pos)}.')
        else:
            api.dump_follow(name)
    except FileNotFoundError:
        print(f'\x1b[91mUnable to find "{name}".')
    return ParseResult(ParseStatus.RAW)


def cmd_generic(api: base.api_base, head: str, body: str, level=0) -> ParseResult:
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


# Converts constructs of "[[%s]]" or "([%s])" into an rsexec command.
def _parse_encap(api: base.api_base, encap: str, encap_i: int, level=0) -> str:
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
        return parse_str(api, trim, level=level + 1)
    return encap


def _param_single(api: base.api_base, body: str, level=0) -> str:
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
    api: base.api_base,
    body: str,
    default="nil",
    level=0,
    max_split=-1,
    min_params=0,
    *_a,
    **_kwa,
) -> list[str]:
    encap_map: dict[str, str] = {
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
    escaped: bool = False
    encap_l: deque[tuple[int, str]] = deque()

    def finalise(buf: str) -> str:
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


def _parse_rec(api: base.api_base, input_gen=INPUT_GEN, level=0, print=print) -> ParseResult:
    line: str = ""
    first_l: str = next(input_gen, None)  # type: ignore
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
    }

    # One-line snippet.
    if head_l in ["s", "snip", "snippet"]:
        return cmd_snippet(api, body, level)

    elif head_l in ["f", "func", "function"]:
        return cmd_function(api, body, level)

    # Single-statement function; 'return' is prepended.
    elif head_l in ["l", "lambda"]:
        return cmd_lambda(api, body, level)

    # Treats each parameter as its own statement, outputs each to the console.
    elif head_l in ["o", "output"]:
        return cmd_output(api, body, level)

    # Multi-line script.
    elif head_l in ["ml", "m", "multiline"]:
        return cmd_multiline(api, input_gen, body, level)

    # Lists Lua files in the workspace folder.
    elif head_l in ["list"]:
        return cmd_list()

    elif head_l in ["repeat"]:
        return cmd_repeat(api, body, level)

    elif head_l in ["b", "batch"]:
        return cmd_batch(api, body, level)

    # Loads Lua(u) code from a URL.
    elif head_l in ["ls", "loadstring"]:
        return cmd_loadstring(api, body, level)

    # Generates help page for the given command alias.
    elif head_l in ["man"]:
        return cmd_man(api, body, level)

    elif head_l in ["dump"] and not level:
        return cmd_dump(api, body, level)

    elif head_l in ["r", "reset", "restart"]:
        return ParseResult(ParseStatus.RESTART)

    # Clears the console.
    elif head_l in ["cl", "cls", "clr", "clear"]:
        return ParseResult(ParseStatus.CLEAR)

    elif head_l == ["e", "exit"]:
        return ParseResult(ParseStatus.EXIT)

    else:
        return cmd_generic(api, head, body, level)


def parse_str(api: base.api_base, string: str, level=0) -> str:
    g = (_ for _ in [string])
    res: ParseResult = _parse_rec(api, input_gen=g, level=level)
    return res.script


def parse(api: base.api_base, input_gen=INPUT_GEN, print=print) -> ParseResult:
    return _parse_rec(api, input_gen=input_gen, level=0, print=print)


def process(api: base.api_base, input_gen=INPUT_GEN) -> None:
    try:
        while True:
            script_lines = None
            print("\x1b[00m> \033[93m", end="")
            result = parse(api, input_gen, print)
            out_n = api.output_call('"\\0"')
            out_e = api.output_call('"\x1b[91m"..e')
            err_b = f"if not s then\n{out_e}\nend"
            msg_e = "Syntax error; perhaps check the devconsole."
            err_s = api.output_call(f'"\x1b[91m{msg_e}\\0"')
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
                anything = api.output_follow()
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
    except Exception:
        pass
    finally:
        print("\033[00m", end="")
