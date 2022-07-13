import os
import shlex
import clr

clr.AddReference("System.Net")
import System.Net

# Quick hack to take care of TLS problems on the WRD side.
System.Net.ServicePointManager.SecurityProtocol = System.Net.SecurityProtocolType(16320)
os.chdir(os.path.dirname(__file__))

clr.AddReference("WeAreDevs_API")
import WeAreDevs_API

clr.AddReference("EasyExploits")
import EasyExploits

clr.AddReference("OxygenU_API")
import OxygenU_API


class exec_api:
    ex: any

    def exec(self, script: str):
        raise NotImplementedError()

    def is_attached(self):
        raise NotImplementedError()


class api_wrd(exec_api):
    def __init__(self):

        self.ex = WeAreDevs_API.ExploitAPI()
        self.ex.LaunchExploit()
        while not self.is_attached():
            input("Hit enter when injection is done!")

    def exec(self, script: str):
        if not self.is_attached():
            raise RuntimeError("WRD API is not injected.")
        return self.ex.SendLuaScript(script)

    def is_attached(self):
        return self.ex.isAPIAttached()


class api_eze(exec_api):
    def __init__(self):
        self.ex = EasyExploits.Module()
        self.ex.LaunchExploit()
        if not self.is_attached():
            raise RuntimeError("Unable to inject EasyExploits API.")

    def exec(self, script: str):
        if not self.is_attached():
            raise RuntimeError("EasyExploits API is not injected.")
        return self.ex.ExecuteScript(script)

    def is_attached(self):
        return self.ex.isInjected()


class api_oxy(exec_api):
    def __init__(self):
        self.ex = OxygenU_API.Client()
        self.ex.Attach()
        if not self.is_attached():
            raise RuntimeError("Unable to inject OxygenU API.")

    def exec(self, script: str):
        if not self.is_attached():
            raise RuntimeError("OxygenU API is not injected.")
        return self.ex.Execute(script)

    def is_attached(self):
        return self.ex.isOXygenUAttached()


class exec_in:
    api: exec_api

    def __init__(self, api: exec_api):
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
        if head == "snippet":
            lines = [body]
            while True:
                s_line = next(input_gen).strip()
                lines.append(s_line)
                if len(s_line) == 0:
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
    api = api_wrd()
    print("Executor has been successfully injected.")
    in_obj = exec_in(api)
    while True:
        in_obj.process()
