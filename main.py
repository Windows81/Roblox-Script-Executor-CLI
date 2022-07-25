import exec_wearedevs
import exec_base
import clr
import os

clr.AddReference("System.IO")
import System.IO

clr.AddReference("System.IO.Pipes")
import System.IO.Pipes

clr.AddReference("System.Net")
import System.Net


class exec_processor:
    api: exec_base.exec_api

    def __init__(self, api: exec_base.exec_api):
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
        input_gen = self._input(f, *args, **kwargs)
        line = next(input_gen)
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

        elif head == "exit":
            exit()

        elif head == "list":
            for p in os.listdir("workspace"):
                if p.lower().endswith("lua"):
                    print(f"- {p}")

        else:
            join = "".join(f", {s}" for s in self._params(body))
            script_body = f'exec("{head}"{join})'

        if script_body:
            return self.api.exec(script_body)


if __name__ == "__main__":
    api = exec_wearedevs.api_wrd_exe()
    print("Executor has been successfully injected.")
    in_obj = exec_processor(api)
    while True:
        in_obj.process()
