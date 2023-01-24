from dataclasses import dataclass
import executors.base as base
from collections import deque
from io import BufferedReader
from functools import cache
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


@cache
def ansi_code(code: str = '00') -> str:
    return f'\x1b[{code}m'


def _func_head(arg_u) -> str:
    if not arg_u:
        arg_u = "nil"
    arg_t = f"local A={{{arg_u}}}"
    arg_n = f"local {','.join(f'a{n}' for n in range(1,10))}={arg_u}"
    return f"""
    {arg_t}
    {arg_n}
    """


def cmd_snippet(api: base.api_base, body: str, level=0) -> ParseResult:
    s_body = _param_single(api, body, level=level)
    return ParseResult(ParseStatus.SYNC, s_body)


def cmd_function(api: base.api_base, body: str, level=0) -> ParseResult:
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level)
    f_str = f"(function(...) {arg_h} {f_body} end)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_lambda(api: base.api_base, body: str, level=0) -> ParseResult:
    arg_h = _func_head("...")
    f_body = _param_single(api, body, level=level)
    f_str = f"(function(...) {arg_h} return {f_body} end)"
    return ParseResult(ParseStatus.RAW, f_str)


def cmd_output(api: base.api_base, body: str, level=0) -> ParseResult:
    param_l = _param_list(api, body, level=level)
    o_table = "\n".join(f"{{{alias}}}," for alias in param_l)
    return ParseResult(
        ParseStatus.SYNC,
        f"""
        (function(...)
            for i,t in next,{{{o_table}}}do
                if i>1 then
                    {api.output_call(f"'{ansi_code()}; '")}
                end
                if t then
                    for i,v in next,t do
                        if i>1 then
                            {api.output_call(f"'{ansi_code()}; '")}
                        end
                        {api.output_call("v")}
                    end
                end
                {api.output_call(repr(chr(10))) if level else ""}
                _E.OUTPUT=nil
            end
        end)()
        """,
    )


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
    [var, cmd] = _param_list(api, body, level=level, max_split=1, min_params=2)
    return ParseResult(
        ParseStatus.SYNC,
        f"""
        (function()
            local T={{}}
            if typeof({var})=='table'then
                for I,V in next,({var})do
                    T[I]={parse_str(api, cmd, level=level)}
                end
            else
                for I=1,({var})do
                    T[I]={parse_str(api, cmd, level=level)}
                end
            end
            return T
        end)()
        """,
    )


def cmd_batch(api: base.api_base, body: str, level=0) -> ParseResult:
    [var, sb] = _param_list(api, body, level=level, max_split=1, min_params=2)

    return ParseResult(
        ParseStatus.SYNC,
        f"""
        (function()
            for I=1,({var})do
                {sb}
            end
        end)
        """,
    )


def cmd_loadstring(api: base.api_base, body: str, level=0) -> ParseResult:
    [url, *args] = _param_list(api, body, level=level)
    arg_h = _func_head(", ".join(args))
    try:
        script = requests.get(url)
        body = f"(function() {arg_h} {script.text} end)()"
        return ParseResult(ParseStatus.ASYNC, body)

    except requests.exceptions.RequestException as e:
        print(f"{ansi_code('91')}{e.strerror}")
        return ParseResult(ParseStatus.RAW)


def cmd_man(api: base.api_base, body: str, level=0) -> ParseResult:
    alias = _param_single(api, body, level=level)
    if level:
        return ParseResult(ParseStatus.SYNC, f'_E.EXEC("man",{repr(alias)})')

    # Header with command name coloured and in uppercase.
    o_call = api.output_call(
        f"'\\n{ansi_code('93')}'..gsp:upper().."

        # Change colour; begin Lua gsub chain.
        + f"':\\n{ansi_code('94')}'..man"

        # Convert line breaks from CRLF to LF.
        + ":gsub('\\r\\n','\\n')"

        # Remove lines which begin in "--".
        + ":gsub('\\n%-%-[^\\n]+','\\n')"

        # Change parameter numbering format; also add some colour.
        + f"""
        :gsub('%[(%d+)%] %- ([^\\n]+)\\n([^%[]+)', '{ansi_code('91')}%1) {ansi_code('92')}%2{ansi_code('90')}\\n%3')
        :gsub('\\n\\t','\\n    ')
        """

        # Restore to original colour.
        + f'.."\\n{ansi_code()}"'
    )

    # In case of inability to resolve path (add "\0" to tell program to receive input).
    gsp_e = f'"{ansi_code("91")}Alias does not exist.{ansi_code()}\\0"'

    # In case of found script lacking docstring (add "\0" to tell program to receive input).
    man_e = f'"{ansi_code("91")}Alias does not have \\"help\\" metatext.{ansi_code()}\\0"'

    return ParseResult(
        ParseStatus.SYNC,
        f"""
        local gsp=_E.GSP({repr(alias)})
        if not gsp then
            {api.output_call(gsp_e)}
            return
        end
        local man=_E.EXEC('man',{repr(alias)})
        if not man then
            {api.output_call(man_e)}
            return
        end
        {o_call}
        """,
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
        print(ansi_code(), end="")
        if sub.lower() == "reset":
            pos = api.dump_reset(name)
            print(f'Reset "{name}" from byte {hex(pos)}.')
        else:
            api.dump_follow(name)
    except FileNotFoundError:
        print(f'{ansi_code("91")}Unable to find "{name}".')
    return ParseResult(ParseStatus.RAW)


def cmd_find_path(api: base.api_base, body: str, level=0) -> ParseResult:
    param_l = _param_list(api, body, level=level)
    o_table = f'{{{"".join(f"_E.FIND_PATH({repr(alias)}) or false," for alias in param_l)}}}'
    if level:
        return ParseResult(ParseStatus.SYNC, o_table)

    return ParseResult(
        ParseStatus.SYNC,
        f"""
        (function(...)
            for i,v in next,{o_table}do
                if i>1 then
                    {api.output_call(f"'{ansi_code()}; '")}
                end
                if v then
                    {api.output_call("v")}
                else
                    {api.output_call(repr(f'{ansi_code("91")}nil{ansi_code()}'))}
                end
                _E.OUTPUT=nil
            end
        end)()
        """,
    )


def cmd_path_list(api: base.api_base, body: str, level=0) -> ParseResult:
    param_l = _param_list(api, body, level=level)
    o_table = f'{{{"".join(f"_E.PATH_LIST({repr(alias)})," for alias in param_l)}}}'
    if level:
        return ParseResult(ParseStatus.SYNC, o_table)

    return ParseResult(
        ParseStatus.SYNC,
        f"""
        (function(...)
            for i,t in next,{o_table}do
                if i>1 then
                    {api.output_call(f"'{ansi_code()}; '")}
                end
                for i,v in next,t do
                    if i>1 then
                        {api.output_call(f"'{ansi_code()}; '")}
                    end
                    {api.output_call("v")}
                end
                _E.OUTPUT=nil
            end
        end)()
        """,
    )


def cmd_generic(api: base.api_base, head: str, body: str, level=0) -> ParseResult:
    pl = _param_list(api, body, level=level)
    join = "".join(f", {s}" for s in pl)
    result = f'_E.EXEC("{head}"{join})'
    if level:
        return ParseResult(ParseStatus.SYNC, result)

    # Prints the returned output script of a command if we're on a top-level parse.
    return ParseResult(
        ParseStatus.SYNC,
        f"""
        local r={{{result}}}
        local t=_E.OUTPUT or r
        if t then
            for i,v in next,t do
                if i>1 then
                    {api.output_call(f"'{ansi_code()}; '")}
                end
                {api.output_call('v')}
            end
        end
        """,
    )


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

    elif head_l in ["find", "find-path", "path"]:
        return cmd_find_path(api, body, level)

    elif head_l in ["pl", "path-list", "paths"]:
        return cmd_path_list(api, body, level)

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
            print(f"{ansi_code()}> {ansi_code('93')}", end="")
            result = parse(api, input_gen, print)
            zero_chr = '\\0'

            # Uniquely generated Lua flag name whose value:
            # 1. is initially false,
            # 2. becomes true when we run the script, and
            # 3. becomes false again if success.
            var = f"_E.RUN{str(time.time()).replace('.','')}"

            if result.status == ParseStatus.SYNC:
                msg_e = "Syntax error; perhaps check the devconsole."

                script_lines = [
                    # Run script block wrapped in Lua pcall, then allow Rsexec to request input after 0.2 seconds.
                    # Also ensure {result.script} is in the first line to ensure accurate exception handline.
                    f"""
                    {var}=true local s,e=pcall(function() {result.script}; end)
                    if not s then
                        api.output_call(f'"{ansi_code("91")}"..e')
                    end
                    task.wait(0.2)
                    {api.output_call(f'"{zero_chr}"')}
                    {var}=false
                    """,

                    # Syntax error protection: check a few times if the flag was set to true in the other snippet.
                    f"""
                    local c=7
                    repeat c=c-1
                    task.wait(0)
                    if {var} then
                    return
                    end
                    until c==0
                    {api.output_call(f'"{ansi_code("91")}{msg_e}{zero_chr}"')}
                    """,
                ]

            elif result.status == ParseStatus.ASYNC:
                script_lines = [
                    f"""
                    local s,e=pcall(function() {result.script}; end)
                    if not s then
                        {api.output_call(f'"{ansi_code("91")}"..e')}
                    end
                    {api.output_call(f'"{zero_chr}"')}
                    """,
                ]

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

            print(ansi_code(), end="")
            try:
                anything = api.output_follow()
                print(f"", end="\n" if anything else "")
            except KeyboardInterrupt:
                print(
                    f"{ansi_code('91')}Process is still running; future output may be garbled.",
                    end="\n",
                )

    except KeyboardInterrupt:
        pass
    except EOFError:
        pass
    except Exception:
        pass
    finally:
        print(ansi_code(), end="")
