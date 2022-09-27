/**
 * Copyright (c) 2022 aiocat
 *
 * This software is released under the MIT License.
 * https://opensource.org/licenses/MIT
 */

#include "./inject.h"

InjectionStatus Inject(void)
{
    HANDLE injectorDll = LoadLibrary(TEXT("injector.dll"));
    if (!injectorDll)
        return Failure;

    char krnlDllPath[1025] = { 0 };
    if (GetFullPathName("krnl.dll", 1025, krnlDllPath, NULL) == 0)
    {
        FreeLibrary(injectorDll);
        return KrnlDllNotFound;
    }

    INJECT_FUNCTION injectFunction = (INJECT_FUNCTION)GetProcAddress(injectorDll, "inject");
    InjectionStatus result = (*injectFunction)(krnlDllPath);

    FreeLibrary(injectorDll);
    return result;
}