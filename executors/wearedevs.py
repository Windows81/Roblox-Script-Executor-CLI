import executors.base as base
import subprocess
import requests
import clr

clr.AddReference("System.Net")
import System.Net

# Quick hack to take care of TLS problems on WeAreDevs_API.dll.
System.Net.ServicePointManager.SecurityProtocol = System.Net.SecurityProtocolType(16320)

clr.AddReference("WeAreDevs_API")
import WeAreDevs_API


class api_wrd_dll(base.api_base):
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


# TODO: get 32-bit DLL to properly inject into 64-bit RobloxPlayerBeta.
class api_wrd_inj(base.api_inj, base.api_upd):
    FILE_PATH = "exploit-main.dll"
    JSON_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"

    def exec(self, script: str):
        self._write_pipe(script, "WeAreDevsPublicAPI_Lua")

    @staticmethod
    def update():
        data = requests.get(api_wrd_inj.JSON_URL).json()
        if data["exploit-module"]["patched"]:
            raise FileNotFoundError()
        url = data["exploit-module"]["download"]

        with open(api_wrd_inj.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)


class api_wrd_exe(base.api_inj, base.api_upd):
    FILE_PATH = "finj.exe"
    JSON_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"
    PROCESS: subprocess.Popen

    def __init__(self):
        self.PROCESS = subprocess.Popen(
            [self.FILE_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        while True:
            l = self.PROCESS.stdout.readline()
            if b"Could not find call!" in l:
                break
            if b"Injected" in l:
                break
        self.PROCESS.communicate()

    def exec(self, script: str):
        self._write_pipe(script, "WeAreDevsPublicAPI_Lua")

    @staticmethod
    def update():
        data = requests.get(api_wrd_exe.JSON_URL).json()
        if data["exploit-module"]["patched"]:
            raise FileNotFoundError()
        url = data["qdRFzx_exe"]

        with open(api_wrd_exe.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)
