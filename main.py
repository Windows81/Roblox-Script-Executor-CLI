import shlex
import clr

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

    def process(self, f=input, *args, **kwargs):
        def cast_to_type(s):
            try:
                return float(s)
            except ValueError:
                return s

        input_gen = self._input(f, *args, **kwargs)
        line = next(input_gen)
        head, body = (*line.split(" ", 1), None)[0:2]
        if head == "script":
            lines = [body]
            while True:
                s_line = next(input_gen).strip()
                lines.append(s_line)
                if len(s_line) == 0:
                    break
            script_body = "\n".join(lines)

        else:
            join = "".join(f", {s}" for s in shlex.split(body, posix=False))
            script_body = f'exec("{head}"{join})'

        if script_body:
            return self.api.exec(script_body)


if __name__ == "__main__":
    api = api_wrd()
    in_obj = exec_in(api)
    while True:
        in_obj.process()
