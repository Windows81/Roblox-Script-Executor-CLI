import subprocess
import executors.base as base
import requests


class api_krnl_exe(base.api_inj, base.api_upd):
    EXE_PATH = "ckrnl.exe"
    DLL_PATH = "krnl.dll"
    DLL_URL = "https://k-storage.com/bootstrapper/files/krnl.dll"

    def __init__(self):
        super().__init__()
        self.PROCESS = subprocess.Popen(
            [self.EXE_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        code = self.PROCESS.wait()
        if code != 0:
            raise ConnectionError(f"Fatal: ckrnl.exe returned exit code {code}!")

    def exec(self, script: str):
        self._write_pipe(script, "krnlpipe")

    @staticmethod
    def update():
        with open(api_krnl_exe.DLL_PATH, "wb") as f:
            f.write(requests.get(api_krnl_exe.DLL_URL).content)
