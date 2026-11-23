#define UNICODE
#define _UNICODE
#define _WIN32_WINNT 0x0600
#include <windows.h>
#include <shlobj.h>
#include <bcrypt.h>
#include <wchar.h>
#include <stdlib.h>
/* Sends the app's existing quit IPC and waits on that server process only.
   No process-name matching, taskkill, or termination of unrelated Python apps. */
int WINAPI wWinMain(HINSTANCE a,HINSTANCE b,LPWSTR args,int show) {
    PWSTR local=NULL;
    if (FAILED(SHGetKnownFolderPath(&FOLDERID_LocalAppData,0,NULL,&local)))return 2;
    wchar_t path[32768];
    int n=_snwprintf(path,32768,L"%ls\\Mars\\HanroroDesktop",local);CoTaskMemFree(local);
    if(n<0)return 2;
    int length=WideCharToMultiByte(CP_UTF8,0,path,-1,NULL,0,NULL,NULL);
    char *utf8=malloc(length);if(!utf8)return 2;
    WideCharToMultiByte(CP_UTF8,0,path,-1,utf8,length,NULL,NULL);
    BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;DWORD objectSize=0,received=0;BYTE digest[32];BYTE *object=NULL;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0){free(utf8);return 2;}
    if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,(BYTE*)&objectSize,sizeof(objectSize),&received,0)<0)goto hash_error;
    object=malloc(objectSize);if(!object)goto hash_error;
    if(BCryptCreateHash(algorithm,&hash,object,objectSize,NULL,0,0)<0)goto hash_error;
    if(BCryptHashData(hash,(BYTE*)utf8,length-1,0)<0||BCryptFinishHash(hash,digest,sizeof(digest),0)<0)goto hash_error;
    BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);free(object);free(utf8);
    wchar_t pipe[80]=L"\\\\.\\pipe\\hanroro-";size_t offset=wcslen(pipe);
    for(int i=0;i<8;i++)_snwprintf(pipe+offset+i*2,3,L"%02x",digest[i]);
    HANDLE channel=CreateFileW(pipe,GENERIC_READ|GENERIC_WRITE,0,NULL,OPEN_EXISTING,0,NULL);
    if(channel==INVALID_HANDLE_VALUE && GetLastError()==ERROR_PIPE_BUSY){WaitNamedPipeW(pipe,3000);channel=CreateFileW(pipe,GENERIC_READ|GENERIC_WRITE,0,NULL,OPEN_EXISTING,0,NULL);}
    if(channel==INVALID_HANDLE_VALUE){DWORD e=GetLastError();return (e==ERROR_FILE_NOT_FOUND||e==ERROR_PATH_NOT_FOUND)?0:3;}
    ULONG pid=0;GetNamedPipeServerProcessId(channel,&pid);
    HANDLE process=pid?OpenProcess(SYNCHRONIZE,FALSE,pid):NULL;
    DWORD sent=0;BOOL ok=WriteFile(channel,"quit",4,&sent,NULL);CloseHandle(channel);
    if(!ok||sent!=4){if(process)CloseHandle(process);return 3;}
    if(!process)return 3;
    DWORD result=WaitForSingleObject(process,12000);CloseHandle(process);return result==WAIT_OBJECT_0?0:4;
hash_error:
    if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);free(object);free(utf8);return 2;
}
