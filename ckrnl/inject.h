/**
 * Copyright (c) 2022 aiocat
 *
 * This software is released under the MIT License.
 * https://opensource.org/licenses/MIT
 */

#ifndef _CKRNL_INJECT_H
#define _CKRNL_INJECT_H

#include <windows.h>
#include <stdlib.h>

typedef enum InjectionStatus
{
    Failure = -1,
    Success = 0,
    LoadImageFail,
    NoRobloxProcess,
    KrnlDllNotFound,
} InjectionStatus;

typedef InjectionStatus(*INJECT_FUNCTION)(const char*);

InjectionStatus Inject(void);

#endif