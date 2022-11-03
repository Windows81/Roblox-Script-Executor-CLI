import executors.base as base
import subprocess
import requests


class api_krnl_exe(base.api_inj, base.api_upd):
    EXE_PATH = "ckrnl.exe"
    DLL_PATH = "krnl.dll"
    DLL_URL = "https://k-storage.com/bootstrapper/files/krnl.dll"
    PIPE_NAME = "krnlpipe"

    def restart(self) -> None:
        self.PROCESS = subprocess.Popen(
            [self.EXE_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        code = self.PROCESS.wait()
        if code != 0:
            raise ConnectionError(
                f"Fatal: ckrnl.exe returned exit code {code}!")
        super().restart()

    @staticmethod
    def update() -> None:
        with open(api_krnl_exe.DLL_PATH, "wb") as f:
            f.write(requests.get(api_krnl_exe.DLL_URL).content)
