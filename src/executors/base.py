import io
import os
import clr
import time
import ctypes
import win32api
import win32con
import win32event
import win32process
import ctypes.wintypes
import win32com.client
from typing_extensions import Self

try:
    clr.AddReference("System.IO")  # type: ignore
    import System.IO  # type: ignore

    clr.AddReference("System.IO.Pipes")  # type: ignore
    import System.IO.Pipes  # type: ignore

    clr.AddReference("System.Net")  # type: ignore
    import System.Net  # type: ignore
except ImportError:
    pass


class api_base:
    _instances: dict[str, Self] = {}
    _first_time: bool = True

    OUTPUT_IO: io.BufferedReader
    _workspace_dir: str = "workspace"
    _output_path: str

    # It's messy here because I'm trying to enforce the singleton model.
    def __new__(cls, output="_output.dat") -> Self:
        if output in api_base._instances:
            return api_base._instances[output]
        item = api_base._instances[output] = super().__new__(cls)
        item._output_path = output

        item.restart()
        item._first_time = False
        return item

    def restart(self) -> None:
        # (Re)opens the output stream for console evaluation.
        dump: str = os.path.join(self._workspace_dir, self._output_path)
        if self.OUTPUT_IO:
            self.OUTPUT_IO.close()
        with open(dump, "wb") as _:
            pass
        self.OUTPUT_IO = open(dump, "rb")

        # Writes code that properly outputs to our console onto "workspace/output.lua".
        olua: str = os.path.join(self._workspace_dir, "output.lua")
        with open(olua, "w") as f:
            f.write(f"_E.RETURN={self.output_call('_E.ARGS[1]')}")

    def output_call(self, s, suffix="nil") -> str:
        return f"_E.EXEC('save',{repr(self._output_path)},{s},{suffix},true)"

    def exec(self, _: str) -> None:
        raise NotImplementedError()

    def is_attached(self) -> bool:
        raise NotImplementedError()

    def __del__(self) -> None:
        self.OUTPUT_IO.close()

    def follow_output(self) -> bool:
        data: bytes = bytes()
        while True:
            data = self.OUTPUT_IO.read()
            if not data:
                time.sleep(0)
                continue
            break

        tries: float = 1e5
        processed: bool = False
        splice: bytes
        while tries > 0:
            if data:
                if data[-1] == 0:
                    splice = data[:-1]
                    tries = 1e3
                else:
                    splice = data
                    tries = 2e5
                if splice:
                    ps = splice.decode("utf-8")
                    print(ps, end="")
                    processed = True
            else:
                tries -= 1
            time.sleep(0)
            data = self.OUTPUT_IO.read()
        return processed


class api_inj(api_base):
    PIPE_NAME: str

    def restart(self) -> None:
        pipe_args = [".", self.PIPE_NAME, System.IO.Pipes.PipeDirection.Out]
        while True:
            try:
                pipe = System.IO.Pipes.NamedPipeClientStream(*pipe_args)
                pipe.Connect(100)
                pipe.Dispose()
                break
            except System.TimeoutException:
                continue
        super().restart()

    def _write_pipe(self, body: str) -> None:
        try:
            pipe_args = [".", self.PIPE_NAME,
                         System.IO.Pipes.PipeDirection.Out]
            pipe = System.IO.Pipes.NamedPipeClientStream(*pipe_args)
            pipe.Connect(666)

            writer_args = [pipe]
            writer = System.IO.StreamWriter(*writer_args)
            writer.Write(body)
            writer.Dispose()
            pipe.Dispose()
        except System.TimeoutException:
            raise ConnectionError("Fatal: unable to connect to pipe.")

    def exec(self, script: str) -> None:
        self._write_pipe(script)

    # https://github.com/penghwee-sng/penetration-testing-snippets/blob/2d3ed6ee547657c3dc36951bf186dea9a3950af7/dll/dll_injector.py
    def _inject(self, path: str) -> None:
        path_b: bytes = bytes(os.path.abspath(path), "ascii")
        proc_id: int = -1
        _wmi = win32com.client.GetObject('winmgmts:')
        for process in _wmi.ExecQuery('Select * from win32_process'):
            if (
                process.Name == "RobloxPlayerBeta.exe"
                and "--play" in process.CommandLine
            ):
                proc_id = process.pid
                break

        if proc_id == -1:
            raise ProcessLookupError()

        process_handle = win32api.OpenProcess(
            win32con.PROCESS_ALL_ACCESS, False, proc_id
        )
        memory_address = win32process.VirtualAllocEx(
            process_handle,
            0,
            len(path_b),
            win32con.MEM_COMMIT | win32con.MEM_RESERVE,
            win32con.PAGE_READWRITE,
        )

        k32 = ctypes.windll.kernel32
        bytes_written = ctypes.c_int(0)
        k32.WriteProcessMemory(
            int(process_handle),
            memory_address,
            path_b,
            len(path_b),
            ctypes.byref(bytes_written),
        )

        k32_handle = win32api.GetModuleHandle("kernel32.dll")
        load_library_a_address = win32api.GetProcAddress(
            k32_handle, b"LoadLibraryA")  # type: ignore
        remote_data = win32process.CreateRemoteThread(
            process_handle, None, 0, load_library_a_address, memory_address, 0  # type: ignore
        )

        event_state = win32event.WaitForSingleObjectEx(
            remote_data[0], 60 * 1000, False)
        if event_state == win32event.WAIT_TIMEOUT:
            print("Injected DllMain thread timed out.")


class api_upd(api_base):
    FILE_PATH: str

    def restart(self) -> None:
        super().restart()

    def _load(self) -> bytes | None:
        if os.path.isfile(self.FILE_PATH):
            with open(self.FILE_PATH, "rb") as f:
                return f.read()
        else:
            self.update()

    @staticmethod
    def update():
        raise NotImplementedError()
