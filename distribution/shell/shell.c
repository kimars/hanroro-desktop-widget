#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdlib.h>
#include <wchar.h>
/* No keystrokes are stored. Only a standalone Win press is consumed; chords replay normally. */
static HHOOK hook;static HWND search;static int held=0,chord=0;static DWORD winkey=VK_LWIN;
static HWND bars[64];static DWORD owners[64];static int count=0;
static int isbar(HWND w){wchar_t c[80]={0};GetClassNameW(w,c,80);return !wcscmp(c,L"Shell_TrayWnd")||!wcscmp(c,L"Shell_SecondaryTrayWnd");}
static BOOL CALLBACK hidebar(HWND w,LPARAM l){int i;DWORD pid;if(!isbar(w))return TRUE;for(i=0;i<count;i++)if(bars[i]==w){ShowWindow(w,SW_HIDE);return TRUE;}if(count<64&&IsWindowVisible(w)){GetWindowThreadProcessId(w,&pid);bars[count]=w;owners[count++]=pid;ShowWindow(w,SW_HIDE);}return TRUE;}
static void restore(void){int i;DWORD pid;for(i=0;i<count;i++){GetWindowThreadProcessId(bars[i],&pid);if(pid==owners[i]&&isbar(bars[i]))ShowWindow(bars[i],SW_SHOWNA);}count=0;}
static void key(DWORD vk,DWORD scan,DWORD flags){INPUT in;ZeroMemory(&in,sizeof(in));in.type=INPUT_KEYBOARD;in.ki.wVk=(WORD)vk;in.ki.wScan=(WORD)scan;in.ki.dwFlags=flags;SendInput(1,&in,sizeof(in));}
static LRESULT CALLBACK keyboard(int code,WPARAM message,LPARAM param){
 if(code>=0){KBDLLHOOKSTRUCT *k=(KBDLLHOOKSTRUCT*)param;int down=message==WM_KEYDOWN||message==WM_SYSKEYDOWN;
 if(k->flags&LLKHF_INJECTED)return CallNextHookEx(hook,code,message,param);
 if(k->vkCode==VK_LWIN||k->vkCode==VK_RWIN){
  if(down){if(!held){if((GetAsyncKeyState(VK_CONTROL)|GetAsyncKeyState(VK_MENU)|GetAsyncKeyState(VK_SHIFT))&0x8000)return CallNextHookEx(hook,code,message,param);held=1;chord=0;winkey=k->vkCode;}return 1;}
  if(held){if(chord)key(winkey,0,KEYEVENTF_KEYUP);else PostMessageW(search,WM_APP+441,0,0);held=0;chord=0;return 1;}
 }else if(held&&down&&!chord){INPUT in[2];ZeroMemory(in,sizeof(in));chord=1;in[0].type=in[1].type=INPUT_KEYBOARD;in[0].ki.wVk=(WORD)winkey;in[1].ki.wVk=(WORD)k->vkCode;in[1].ki.wScan=(WORD)k->scanCode;in[1].ki.dwFlags=(k->flags&LLKHF_EXTENDED)?KEYEVENTF_EXTENDEDKEY:0;SendInput(2,in,sizeof(INPUT));return 1;}
 }return CallNextHookEx(hook,code,message,param);
}
int wmain(int argc,wchar_t **argv){
 HANDLE parent,stop,handles[2];MSG m;int hide,win;DWORD pid,state;if(argc!=6)return 2;
 pid=wcstoul(argv[1],0,10);search=(HWND)(UINT_PTR)_wcstoui64(argv[2],0,10);hide=_wtoi(argv[3]);win=_wtoi(argv[4]);
 parent=OpenProcess(SYNCHRONIZE,FALSE,pid);stop=OpenEventW(SYNCHRONIZE,FALSE,argv[5]);
 if(!parent||!stop||!IsWindow(search)){if(parent)CloseHandle(parent);if(stop)CloseHandle(stop);return 3;}
 if(win){hook=SetWindowsHookExW(WH_KEYBOARD_LL,keyboard,GetModuleHandleW(NULL),0);if(!hook){CloseHandle(parent);CloseHandle(stop);return 4;}}
 SetTimer(NULL,1,500,NULL);
 handles[0]=parent;handles[1]=stop;
 for(;;){state=MsgWaitForMultipleObjects(2,handles,FALSE,500,QS_ALLINPUT);if(state==WAIT_OBJECT_0||state==WAIT_OBJECT_0+1||!IsWindow(search))break;
 while(PeekMessageW(&m,NULL,0,0,PM_REMOVE)){if(m.message==WM_TIMER){if(hide)EnumWindows(hidebar,0);}else{TranslateMessage(&m);DispatchMessageW(&m);}}}
 if(hook)UnhookWindowsHookEx(hook);if(held&&chord)key(winkey,0,KEYEVENTF_KEYUP);restore();CloseHandle(parent);CloseHandle(stop);return 0;
}
