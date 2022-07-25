import subprocess
import exec_base
import requests
import clr
import os

clr.AddReference("System.Net")
import System.Net

# Quick hack to take care of TLS problems on the WRD side.
System.Net.ServicePointManager.SecurityProtocol = System.Net.SecurityProtocolType(16320)
cdir = os.path.dirname(__file__)
if cdir != "":
    os.chdir(cdir)

clr.AddReference("WeAreDevs_API")
import WeAreDevs_API


class api_wrd(exec_base.exec_api):
    def __init__(self):
        self.ex = WeAreDevs_API.ExploitAPI()
        if not self.ex.LaunchExploit():
            raise SystemError()
        while not self.is_attached():
            input("Hit enter when injection is done!")

    def exec(self, script: str):
        if not self.is_attached():
            raise RuntimeError("WRD API is not injected.")
        return self.ex.SendLuaScript(script)

    def is_attached(self):
        return self.ex.isAPIAttached()


class api_wrd_dll(exec_base.api_inj, exec_base.api_upd):
    FILE_PATH = "exploit-main.dll"
    MODULE_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"

    def exec(self, script: str):
        self._write_pipe(script, "WeAreDevsPublicAPI_Lua")

    def update(self):
        data = requests.get(self.MODULE_URL).json()
        if data["exploit-module"]["patched"]:
            raise FileNotFoundError()
        url = data["exploit-module"]["download"]

        with open(self.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)


class api_wrd_exe(exec_base.api_inj, exec_base.api_upd):
    FILE_PATH = "exploit-main.dll"
    MODULE_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"
    PROCESS: subprocess.Popen

    def __init__(self):
        self.PROCESS = subprocess.Popen(
            ["finj.exe"], stdout=subprocess.PIPE, shell=False
        )
        while True:
            l = self.PROCESS.stdout.readline()
            if b"Could not find call!" in l:
                return
            if b"Injected" in l:
                return

    def exec(self, script: str):
        self._write_pipe(script, "WeAreDevsPublicAPI_Lua")

    def update(self):
        data = requests.get(self.MODULE_URL).json()
        if data["exploit-module"]["patched"]:
            raise FileNotFoundError()
        url = data["exploit-module"]["download"]

        with open(self.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)
