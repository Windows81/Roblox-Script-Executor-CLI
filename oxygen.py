import clr

clr.AddReference("OxygenU_API")
import executors.base as base
import OxygenU_API


class api_oxy(base.api_base):
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