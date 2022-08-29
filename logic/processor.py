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

    def _params(self, body: str) -> list[str]:
        encap_map = {
            "'": "'",
            '"': '"',
            "[": "]",
            "(": ")",
            "{": "}",
        }
        encap_k = "".join(encap_map.keys())
        encap_v = "".join(encap_map.values())
        params = []
        param_buf = ""
        escaped = False
        encap_l = deque()

        def finalise(buf):
            if buf == "":
                buf = "nil"
            return buf

        for i, ch in enumerate(body.split("--", 1)[0].strip()):
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
                last_i, last_c = encap_l.pop()
                param_buf += ch
                if last_i == 0 and last_c == "]":
                    do_parse = True
                elif last_c == ")" or last_c == "]":
                    lmatch = param_buf[last_i + 1] == "["
                    rmatch = param_buf[-2] == "]"
                    do_parse = lmatch and rmatch
                if do_parse:
                    trim = param_buf[last_i:].lstrip(encap_k).rstrip(encap_v)
                    param_buf = param_buf[0:last_i] + self.parse((_ for _ in [trim]))
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
            if ch.isspace():
                params.append(finalise(param_buf))
                param_buf = ""
                continue

            else:
                param_buf += ch
                escaped = False

        params.append(finalise(param_buf))
        return params

    def parse(self, input_gen=_gen(input)):
        line = next(input_gen)
        if len(line.strip()) == 0:
            return
        head, body = (*line.split(" ", 1), "")[0:2]

        # One-line snippet.
        if head == "snippet":
            return body

        # Multi-line script.
        elif head == "script":
            lines = [body]
            while True:
                s_line = next(input_gen, "")
                lines.append(s_line)
                if len(s_line.strip()) == 0:
                    break
            return "\n".join(lines)

        elif head == "list":
            for p in os.listdir("workspace"):
                if p.lower().endswith("lua"):
                    print(f"- {p}")

        elif head == "exit":
            exit()

        join = "".join(f", {s}" for s in self._params(body))
        return f'rsexec("{head}"{join})'

    def process(self, input_gen=_gen(input)):
        try:
            script_body = self.parse(input_gen)
            if script_body:
                return self.api.exec(script_body)
        except KeyboardInterrupt:
            exit()
