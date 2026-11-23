#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
static void fail(const wchar_t *text) {MessageBoxW(NULL,text,L"한로로 바탕화면 위젯",MB_OK|MB_ICONERROR);}
static int run(const wchar_t *runtime,const wchar_t *script,const wchar_t *working,DWORD *code) {
 wchar_t command[32768];if (_snwprintf(command,32768,L"\"%ls\" \"%ls\"",runtime,script)<0)return 0;
 STARTUPINFOW si={0};PROCESS_INFORMATION pi={0};si.cb=sizeof(si);
 if(!CreateProcessW(runtime,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,working,&si,&pi))return 0;
 CloseHandle(pi.hThread);WaitForSingleObject(pi.hProcess,INFINITE);GetExitCodeProcess(pi.hProcess,code);CloseHandle(pi.hProcess);return 1;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR commandLine,int show) {
 wchar_t root[32768],runtime[32768],script[32768],working[32768];DWORD size=GetModuleFileNameW(NULL,root,32768);
 if(!size||size>=32768){fail(L"실행 경로를 읽지 못했습니다.");return 1;}
 wchar_t *last=wcsrchr(root,L'\\');if(!last)return 1;*last=0;
 if(_snwprintf(working,32768,L"%ls\\_internal",root)<0||_snwprintf(runtime,32768,L"%ls\\pythonw.exe",working)<0)return 1;
 if(GetFileAttributesW(runtime)==INVALID_FILE_ATTRIBUTES){fail(L"압축을 모두 풀어주세요. EXE와 _internal 폴더가 함께 있어야 합니다.");return 1;}
 _snwprintf(script,32768,L"%ls\\switch_instance.py",working);DWORD code=0;
 if(!run(runtime,script,working,&code)){fail(L"앱을 시작하지 못했습니다. 압축을 모두 풀었는지 확인해주세요.");return 1;}
 if(code!=0){fail(L"이전 위젯을 트레이에서 종료한 뒤 다시 실행해주세요.");return 1;}
 _snwprintf(script,32768,L"%ls\\main.py",working);
 if(!run(runtime,script,working,&code)){fail(L"앱을 실행하지 못했습니다.");return 1;}
 if(code!=0)fail(L"앱 실행 중 문제가 발생했습니다. _internal 폴더의 app.log를 확인해주세요.");
 return (int)code;
}
