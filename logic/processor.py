from collections import deque
import executors.base as base
import os


class exec_processor:
    api: base.api_base

    def __init__(self, api: base.api_base):
        self.api = api

    def _gen(f=input, *args, **kwargs):
        while (v := f(*args, **kwargs)) != None:
            yield v

    def _parse_encap(self, encap, encap_i):
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
            return self.parse((_ for _ in [trim]))
        return encap

    def _param_single(self, body: str) -> list[str]:
        encap_map = {
            "[": "]",
            "(": ")",
        }
        param_buf = ""
        escaped = False
        encap_l = deque()

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
                result = self._parse_encap(encap, last_i)
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

            else:
                param_buf += ch
                escaped = False
        return param_buf

    def _param_list(self, body: str, default="nil", max_split=-1) -> list[str]:
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
                result = self._parse_encap(encap, last_i)
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

            # Executes if not encapsulates and is a space; adds result to param table and clears buffer.
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

    def parse(self, input_gen=_gen(input)):
        line = next(input_gen).lstrip()
        if len(line) == 0:
            return
        head, body = (*line.split(" ", 1), "")[0:2]
        head_l = head.lower()

        # One-line snippet.
        if head_l in ["snippet", "snip", "s"]:
            return self._param_single(body)

        # Multi-line script.
        elif head_l in ["script", "multiline", "ml", "m"]:
            lines = [body]
            while True:
                s_line = next(input_gen, "")
                lines.append(s_line)
                if len(s_line.strip()) == 0:
                    break
            return self._param_single("\n".join(lines))

        elif head_l in ["list", "l"]:
            for p in os.listdir("workspace"):
                if p.lower().endswith("lua"):
                    print(f"- {p}")
            return None

        elif head_l in ["repeat", "r"]:
            [count, script_body, *_] = self._param_list(body, max_split=1) + 2 * [""]
            return f"for I=1,({count})do\n{script_body}\nend"

        elif head_l == ["exit", "e"]:
            exit()

        join = "".join(f", {s}" for s in self._param_list(body))
        return f'rsexec("{head}"{join})'

    def process(self, input_gen=_gen(input)):
        try:
            script_body = self.parse(input_gen)
            if script_body:
                return self.api.exec(script_body)
        except KeyboardInterrupt:
            exit()
