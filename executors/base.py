import os
import clr
import ctypes
import psutil
import win32api
import win32con
import win32event
import win32process
import ctypes.wintypes

clr.AddReference("System.IO")
import System.IO

clr.AddReference("System.IO.Pipes")
import System.IO.Pipes

clr.AddReference("System.Net")
import System.Net


class api_base:
    ex: any

    def exec(self, script: str):
        raise NotImplementedError()

    def is_attached(self):
        raise NotImplementedError()

    def __del__(self):
        raise ResourceWarning()


class api_inj(api_base):
    def _write_pipe(self, body: str, pipe_name: str):
        pipe_args = [".", pipe_name, System.IO.Pipes.PipeDirection.Out]
        pipe = System.IO.Pipes.NamedPipeClientStream(*pipe_args)
        pipe.Connect(666)

        writer_args = [pipe]
        writer = System.IO.StreamWriter(*writer_args)
        writer.Write(body)
        writer.Dispose()
        pipe.Dispose()

    # https://github.com/penghwee-sng/penetration-testing-snippets/blob/2d3ed6ee547657c3dc36951bf186dea9a3950af7/dll/dll_injector.py
    def _inject(self, path: str) -> None:
        path = bytes(os.path.abspath(path), "ascii")
        proc_id: int = -1
        for process in psutil.process_iter():
            if (
                process.name() == "RobloxPlayerBeta.exe"
                and process.cmdline()[1] == "--play"
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
            len(path),
            win32con.MEM_COMMIT | win32con.MEM_RESERVE,
            win32con.PAGE_READWRITE,
        )

        k32 = ctypes.windll.kernel32
        bytes_written = ctypes.c_int(0)
        k32.WriteProcessMemory(
            int(process_handle),
            memory_address,
            path,
            len(path),
            ctypes.byref(bytes_written),
        )

        k32_handle = win32api.GetModuleHandle("kernel32.dll")
        load_library_a_address = win32api.GetProcAddress(k32_handle, b"LoadLibraryA")
        remote_data = win32process.CreateRemoteThread(
            process_handle, None, 0, load_library_a_address, memory_address, 0
        )

        event_state = win32event.WaitForSingleObjectEx(remote_data[0], 60 * 1000, False)
        if event_state == win32event.WAIT_TIMEOUT:
            print("Injected DllMain thread timed out.")


class api_upd(api_base):
    FILE_PATH: str

    def _load(self):
        if os.path.isfile(self.FILE_PATH):
            with open(self.FILE_PATH, "rb") as f:
                return f.read()
        else:
            self.update()

    @staticmethod
    def update():
        raise NotImplementedError()
