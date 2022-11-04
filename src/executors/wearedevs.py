import executors.base as base
import subprocess
import requests
import clr


def patch_prompt() -> bool:
    p = input("The WeAreDevs API is currently patched. Install? (Y/n) ").lower()
    if p == "n":
        return False
    return True


clr.AddReference("System.IO.Pipes")  # type: ignore
import System.IO.Pipes  # type: ignore

clr.AddReference("System.Net")  # type: ignore
import System.Net  # type: ignore

clr.AddReference("WeAreDevs_API")  # type: ignore
import WeAreDevs_API  # type: ignore

# Quick hack to take care of TLS problems on WeAreDevs_API.dll.
spm = System.Net.ServicePointManager
spm.SecurityProtocol = System.Net.SecurityProtocolType(16320)


class api_wrd_dll(base.api_base):
    def restart(self) -> None:
        self.ex = WeAreDevs_API.ExploitAPI()
        if not self.ex.LaunchExploit():
            raise SystemError()
        while not self.is_attached():
            input("Hit enter when injection is done!")
        super().restart()

    def exec(self, script: str) -> None:
        if not self.is_attached():
            raise RuntimeError("WRD API is not injected.")
        return self.ex.SendLuaScript(script)

    def is_attached(self) -> bool:
        return self.ex.isAPIAttached()


# TODO: get 32-bit DLL to properly inject into 64-bit RobloxPlayerBeta.
class api_wrd_inj(base.api_inj, base.api_upd):
    FILE_PATH = "exploit-main.dll"
    JSON_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"
    PIPE_NAME = "WeAreDevsPublicAPI_Lua"

    def restart(self) -> None:
        raise NotImplementedError(
            "32-bit DLL doesn't work with 64-bit RobloxPlayerBeta."
        )

    @staticmethod
    def update() -> None:
        data = requests.get(api_wrd_inj.JSON_URL).json()
        if data["exploit-module"]["patched"] and not patch_prompt():
            exit()

        url = data["exploit-module"]["download"]
        with open(api_wrd_inj.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)

        url = data["injDep"]
        with open("kernel64.sys.dll", "wb") as f:
            f.write(requests.get(url).content)


class api_wrd_exe(base.api_inj, base.api_upd):
    FILE_PATH = "finj.exe"
    PIPE_NAME = "WeAreDevsPublicAPI_Lua"
    JSON_URL = "https://cdn.wearedevs.net/software/exploitapi/latestdata.json"
    PROCESS: subprocess.Popen

    def restart(self) -> None:
        self.PROCESS = subprocess.Popen(
            [self.FILE_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        super().restart()

    @staticmethod
    def update() -> None:
        data = requests.get(api_wrd_exe.JSON_URL).json()
        if data["exploit-module"]["patched"] and not patch_prompt():
            exit()

        url = data["exploit-module"]["download"]
        with open("exploit-main.dll", "wb") as f:
            f.write(requests.get(url).content)

        url = data["injDep"]
        with open("kernel64.sys.dll", "wb") as f:
            f.write(requests.get(url).content)

        url = data["qdRFzx_exe"]
        with open(api_wrd_exe.FILE_PATH, "wb") as f:
            f.write(requests.get(url).content)
