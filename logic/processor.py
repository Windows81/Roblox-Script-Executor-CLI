import executors.base as base
import os


class exec_processor:
    api: base.api_base

    def __init__(self, api: base.api_base):
        self.api = api

    def _input(self, f=input, *args, **kwargs):
        while True:
            yield f(*args, **kwargs)

    def _params(self, body: str) -> list[str]:
        qm = {
            "'": "'",
            '"': '"',
            "[": "]",
            "(": ")",
            "{": "}",
        }
        w = []
        s = ""
        qc = 0
        q = None
        e = False
        for c in body.split("--", 1)[0].strip():
            if e:
                s += c
                e = False
                continue
            if c == "\\":
                s += c
                e = True
                continue
            if c == qm.get(q, None):
                s += c
                qc -= 1
                if qc == 0:
                    q = None
            elif q:
                if c == q:
                    qc += 1
                s += c
                e = False
            else:
                if c == " ":
                    if s == "":
                        w.append("nil")
                    else:
                        w.append(s)
                    s = ""
                elif c in qm:
                    s += c
                    q = c
                    qc += 1
                else:
                    s += c
                    e = False
        if s == "":
            w.append("nil")
        else:
            w.append(s)
        return w

    def process(self, f=input, *args, **kwargs):
        try:
            input_gen = self._input(f, *args, **kwargs)
            line = next(input_gen)
            if len(line.strip()) == 0:
                return
            head, body = (*line.split(" ", 1), "")[0:2]

            # One-line snippet.
            if head == "snippet":
                script_body = body

            # Multi-line script.
            elif head == "script":
                lines = [body]
                while True:
                    s_line = next(input_gen)
                    lines.append(s_line)
                    if len(s_line.strip()) == 0:
                        break
                script_body = "\n".join(lines)

            elif head == "print":
                script_body = f"print({body})"

            elif head == "list":
                for p in os.listdir("workspace"):
                    if p.lower().endswith("lua"):
                        print(f"- {p}")

            elif head == "exit":
                exit()

            else:
                join = "".join(f", {s}" for s in self._params(body))
                script_body = f'rsexec("{head}"{join})'

            if script_body:
                return self.api.exec(script_body)

        except KeyboardInterrupt:
            exit()
