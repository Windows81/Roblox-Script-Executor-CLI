# TODO: fix OxygenU API.
import OxygenU_API  # type: ignore
import executors.base as base
import clr

clr.AddReference("OxygenU_API")  # type: ignore


class api_oxy(base.api_base):
    def restart(self) -> None:
        self.ex = OxygenU_API.Client()
        self.ex.Attach()
        if not self.is_attached():
            raise RuntimeError("Unable to inject OxygenU API.")
        super().restart()

    def exec(self, script: str) -> None:
        if not self.is_attached():
            raise RuntimeError("OxygenU API is not injected.")
        return self.ex.Execute(script)

    def is_attached(self) -> bool:
        return self.ex.isOXygenUAttached()
