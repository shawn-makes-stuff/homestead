// Homestead's RED4ext plugin: what CET's Lua can't do itself - start Homestead's importer, take the mouse's motion for
// the gizmo, read the game's own key bindings. It starts one program only - the CET mod's importer\HomesteadImport.exe
// (not next to this DLL: RED4ext would take its DLLs for plugins) - never a path or command from a script.
// Natives (r6/scripts/Homestead/HomesteadImport.reds declares them; the mouse's and the keys' further down):
//   HomesteadImportStart(mode: Int32) -> Bool    0 import, 1 a fresh import, 2 only find the games; false: already
//                                                running, or no importer installed
//   HomesteadImportRunning() -> Bool             (any HomesteadImport.exe: one started before the game restarted too)
//   HomesteadImportStop() -> Bool                cancel: the importer and what it started (WolvenKit, its workers)
//   HomesteadImportPath() -> String              the importer's path ("" if it isn't there)
// The import goes on after the game closes (it installs then: the archives are locked while the game runs).
#include <RED4ext/RED4ext.hpp>
#include <windows.h>
#include <tlhelp32.h>
#include <algorithm>
#include <atomic>
#include <string>
#include <vector>

static std::wstring Importer()
{
    HMODULE self = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       reinterpret_cast<LPCWSTR>(&Importer), &self);
    wchar_t buf[MAX_PATH * 2];
    DWORD n = GetModuleFileNameW(self, buf, MAX_PATH * 2);
    std::wstring dir(buf, n);
    for (int up = 0; up < 4; up++) dir = dir.substr(0, dir.find_last_of(L"\\/"));
    return dir + L"\\bin\\x64\\plugins\\cyber_engine_tweaks\\mods\\Homestead\\importer\\HomesteadImport.exe";
}

// the importer's processes (by name: the game may have restarted since it was started), with tree: and every process
// they started, theirs too
static std::vector<DWORD> Importers(bool tree)
{
    std::vector<PROCESSENTRY32W> all;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return {};
    PROCESSENTRY32W e{sizeof(e)};
    for (BOOL ok = Process32FirstW(snap, &e); ok; ok = Process32NextW(snap, &e)) all.push_back(e);
    CloseHandle(snap);
    std::vector<DWORD> out;
    for (auto& p : all)
        if (_wcsicmp(p.szExeFile, L"HomesteadImport.exe") == 0) out.push_back(p.th32ProcessID);
    for (size_t i = 0; tree && i < out.size(); i++)
        for (auto& p : all)
            if (p.th32ParentProcessID == out[i] && std::find(out.begin(), out.end(), p.th32ProcessID) == out.end())
                out.push_back(p.th32ProcessID);
    return out;
}

static bool Running() { return !Importers(false).empty(); }

static bool Stop()
{
    bool any = false;
    for (DWORD pid : Importers(true))
        if (HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pid)) { any = TerminateProcess(h, 1) || any; CloseHandle(h); }
    return any;
}

static bool Start(int mode)
{
    if (Running()) return false;
    std::wstring exe = Importer();
    if (GetFileAttributesW(exe.c_str()) == INVALID_FILE_ATTRIBUTES) return false;
    std::wstring cmd = L"\"" + exe + L"\" --from-game" + (mode == 1 ? L" --force" : mode == 2 ? L" --check" : L"");
    std::wstring dir = exe.substr(0, exe.find_last_of(L"\\/"));
    STARTUPINFOW si{sizeof(si)};
    PROCESS_INFORMATION pi{};
    DWORD flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | BELOW_NORMAL_PRIORITY_CLASS;
    BOOL ok = CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, FALSE, flags | CREATE_BREAKAWAY_FROM_JOB, nullptr,
                             dir.c_str(), &si, &pi);
    if (!ok) ok = CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, FALSE, flags, nullptr, dir.c_str(), &si, &pi);
    if (!ok) return false;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return true;
}

static void ImportStart(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, bool* aOut, int64_t)
{
    int32_t mode = 0;
    RED4ext::GetParameter(aFrame, &mode);
    aFrame->code++;
    bool r = Start(mode);
    if (aOut) *aOut = r;
}

static void ImportRunning(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, bool* aOut, int64_t)
{
    aFrame->code++;
    if (aOut) *aOut = Running();
}

static void ImportStop(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, bool* aOut, int64_t)
{
    aFrame->code++;
    bool r = Stop();
    if (aOut) *aOut = r;
}

static void ImportPath(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, RED4ext::CString* aOut, int64_t)
{
    aFrame->code++;
    std::wstring exe = Importer();
    bool there = GetFileAttributesW(exe.c_str()) != INVALID_FILE_ATTRIBUTES;
    std::string utf8;
    if (there)
    {
        int n = WideCharToMultiByte(CP_UTF8, 0, exe.c_str(), -1, nullptr, 0, nullptr, nullptr);
        utf8.resize(n > 0 ? n - 1 : 0);
        WideCharToMultiByte(CP_UTF8, 0, exe.c_str(), -1, utf8.data(), n, nullptr, nullptr);
    }
    if (aOut) *aOut = RED4ext::CString(utf8.c_str());
}

// // The camera stays as it is without any restriction on it (GameplayRestriction.NoCameraControl drifts); the motion goes to Lua for its cursor.
//   HomesteadMouseSet(on: Bool) -> Bool          on / off; false: the game's window wasn't found (nothing taken)
//   HomesteadMouseX() / HomesteadMouseY() -> Float   the motion since last asked, in the mouse's own counts
static std::atomic<bool> g_mouse{false};
static std::atomic<long> g_dx{0}, g_dy{0};
static WNDPROC g_prev = nullptr;
static HWND g_hwnd = nullptr;

static LRESULT CALLBACK Proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (g_mouse && m == WM_INPUT)
    {
        RAWINPUT ri{};
        UINT sz = sizeof(ri);
        if (GetRawInputData((HRAWINPUT)l, RID_INPUT, &ri, &sz, sizeof(RAWINPUTHEADER)) != (UINT)-1 && ri.header.dwType == RIM_TYPEMOUSE)
        {
            const RAWMOUSE& mo = ri.data.mouse;
            if (!(mo.usFlags & MOUSE_MOVE_ABSOLUTE)) { g_dx += mo.lLastX; g_dy += mo.lLastY; }
            if (mo.usButtonFlags == 0) return DefWindowProcW(h, m, w, l);   // (motion alone: taken - the default proc
        }                                                    // frees the input; a click or the wheel passes, its bit of motion with it)
    }
    return CallWindowProcW(g_prev, h, m, w, l);
}

static BOOL CALLBACK FindGameWindow(HWND h, LPARAM out)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || GetWindow(h, GW_OWNER)) return TRUE;
    RECT r{};
    GetWindowRect(h, &r);
    if ((r.right - r.left) < 300 || (r.bottom - r.top) < 300) return TRUE;   // (the game's own big window, not a helper's)
    *reinterpret_cast<HWND*>(out) = h;
    return FALSE;
}

static bool MouseSet(bool on)
{
    if (!g_hwnd)
    {
        EnumWindows(FindGameWindow, reinterpret_cast<LPARAM>(&g_hwnd));
        if (!g_hwnd) return false;
        g_prev = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(g_hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&Proc)));
        if (!g_prev) { g_hwnd = nullptr; return false; }
    }
    g_dx = 0; g_dy = 0;
    g_mouse = on;
    return true;
}

static void MouseSetNative(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, bool* aOut, int64_t)
{
    bool on = false;
    RED4ext::GetParameter(aFrame, &on);
    aFrame->code++;
    bool r = MouseSet(on);
    if (aOut) *aOut = r;
}

static void MouseXNative(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, float* aOut, int64_t)
{
    aFrame->code++;
    if (aOut) *aOut = static_cast<float>(g_dx.exchange(0));
}

static void MouseYNative(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, float* aOut, int64_t)
{
    aFrame->code++;
    if (aOut) *aOut = static_cast<float>(g_dy.exchange(0));
}

// --- the game's own key bindings, for Homestead's key settings (conflicts) and hint icons -------------------------
//   HomesteadGameKeys() -> String   lines "action|IK_key", one per key of every action live on foot: the
//   Exploration and interaction input contexts (r6\config\inputContexts.xml, includes followed), their mappings'
//   buttons (inputUserMappings.xml), the player's rebinds applied (UserSettings.json "overridableUI" overrides)
static std::string ReadAll(const std::wstring& path)
{
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
    if (h == INVALID_HANDLE_VALUE) return "";
    std::string out;
    char buf[65536];
    DWORD n = 0;
    while (ReadFile(h, buf, sizeof(buf), &n, nullptr) && n > 0) out.append(buf, n);
    CloseHandle(h);
    return out;
}

static std::string Attr(const std::string& s, size_t from, size_t to, const char* name)
{
    std::string key = std::string(name) + "=\"";
    size_t p = s.find(key, from);
    if (p == std::string::npos || p >= to) return "";
    p += key.size();
    size_t e = s.find('"', p);
    if (e == std::string::npos || e > to) return "";
    return s.substr(p, e - p);
}

static std::string GameKeysList()
{
    std::wstring root = Importer();
    for (int up = 0; up < 8; up++) root = root.substr(0, root.find_last_of(L"\\/"));   // \importer\HomesteadImport.exe: 8 up to <game>
    std::string maps = ReadAll(root + L"\\r6\\config\\inputUserMappings.xml");
    std::string ctx = ReadAll(root + L"\\r6\\config\\inputContexts.xml");
    if (maps.empty() || ctx.empty()) return "";
    // the player's rebinds: overridableUI id -> key
    std::vector<std::pair<std::string, std::string>> over;
    wchar_t* local = nullptr;
    if (_wdupenv_s(&local, nullptr, L"LOCALAPPDATA") == 0 && local)
    {
        std::string us = ReadAll(std::wstring(local) + L"\\CD Projekt Red\\Cyberpunk 2077\\UserSettings.json");
        free(local);
        size_t p = 0;
        while ((p = us.find("\"name\": \"", p)) != std::string::npos)
        {
            p += 9;
            size_t e = us.find('"', p);
            if (e == std::string::npos) break;
            std::string name = us.substr(p, e - p);
            size_t v = us.find("\"value\": \"IK_", e);
            size_t nx = us.find("\"name\": \"", e);
            if (v != std::string::npos && (nx == std::string::npos || v < nx))
            {
                v += 10;
                size_t ve = us.find('"', v);
                if (ve != std::string::npos) over.emplace_back(name, us.substr(v, ve - v));
            }
            p = e;
        }
    }
    // mappings: name -> keys (keyboard and mouse, not the pad)
    std::vector<std::pair<std::string, std::vector<std::string>>> mapping;
    size_t p = 0;
    while ((p = maps.find("<mapping ", p)) != std::string::npos)
    {
        size_t end = maps.find("</mapping>", p);
        if (end == std::string::npos) break;
        std::string name = Attr(maps, p, maps.find('>', p), "name");
        std::vector<std::string> keys;
        size_t b = p;
        while ((b = maps.find("<button ", b)) != std::string::npos && b < end)
        {
            size_t be = maps.find("/>", b);
            if (be == std::string::npos || be > end) be = end;
            std::string id = Attr(maps, b, be, "id"), ui = Attr(maps, b, be, "overridableUI");
            if (!ui.empty()) for (auto& o : over) if (o.first == ui) id = o.second;
            if (id.rfind("IK_", 0) == 0 && id.rfind("IK_Pad", 0) != 0) keys.push_back(id);
            b = be;
        }
        if (!name.empty()) mapping.emplace_back(name, keys);
        p = end;
    }
    // contexts: name -> includes, actions (name, map); the ones live on foot, includes followed
    struct Ctx { std::vector<std::string> inc; std::vector<std::pair<std::string, std::string>> acts; };
    std::vector<std::pair<std::string, Ctx>> ctxs;
    p = 0;
    while ((p = ctx.find("<context ", p)) != std::string::npos)
    {
        size_t end = ctx.find("</context>", p);
        if (end == std::string::npos) break;
        Ctx c;
        std::string name = Attr(ctx, p, ctx.find('>', p), "name");
        size_t q = p;
        while ((q = ctx.find('<', q + 1)) != std::string::npos && q < end)
        {
            size_t qe = ctx.find('>', q);
            if (qe == std::string::npos || qe > end) break;
            if (ctx.compare(q, 9, "<include ") == 0) c.inc.push_back(Attr(ctx, q, qe, "name"));
            else if (ctx.compare(q, 8, "<action ") == 0) c.acts.emplace_back(Attr(ctx, q, qe, "name"), Attr(ctx, q, qe, "map"));
            q = qe;
        }
        ctxs.emplace_back(name, c);
        p = end;
    }
    std::vector<std::string> todo = { "Exploration", "InteractionActions", "UIExploration" }, seen;
    std::string out;
    while (!todo.empty())
    {
        std::string n = todo.back(); todo.pop_back();
        if (std::find(seen.begin(), seen.end(), n) != seen.end()) continue;
        seen.push_back(n);
        for (auto& kv : ctxs)
        {
            if (kv.first != n) continue;
            for (auto& i : kv.second.inc) todo.push_back(i);
            for (auto& a : kv.second.acts)
                for (auto& m : mapping)
                    if (m.first == a.second) for (auto& k : m.second) out += a.first + "|" + k + "\n";
        }
    }
    return out;
}

static void GameKeysNative(RED4ext::IScriptable*, RED4ext::CStackFrame* aFrame, RED4ext::CString* aOut, int64_t)
{
    aFrame->code++;
    std::string s = GameKeysList();
    if (aOut) *aOut = RED4ext::CString(s.c_str());
}

RED4EXT_C_EXPORT void RED4EXT_CALL RegisterTypes() {}

RED4EXT_C_EXPORT void RED4EXT_CALL PostRegisterTypes()
{
    auto rtti = RED4ext::CRTTISystem::Get();
    RED4ext::CBaseFunction::Flags flags = {.isNative = true, .isStatic = true};
    auto start = RED4ext::CGlobalFunction::Create("HomesteadImportStart", "HomesteadImportStart", &ImportStart);
    start->flags = flags;
    start->AddParam("Int32", "mode");
    start->SetReturnType("Bool");
    rtti->RegisterFunction(start);
    auto running = RED4ext::CGlobalFunction::Create("HomesteadImportRunning", "HomesteadImportRunning", &ImportRunning);
    running->flags = flags;
    running->SetReturnType("Bool");
    rtti->RegisterFunction(running);
    auto stop = RED4ext::CGlobalFunction::Create("HomesteadImportStop", "HomesteadImportStop", &ImportStop);
    stop->flags = flags;
    stop->SetReturnType("Bool");
    rtti->RegisterFunction(stop);
    auto path = RED4ext::CGlobalFunction::Create("HomesteadImportPath", "HomesteadImportPath", &ImportPath);
    path->flags = flags;
    path->SetReturnType("String");
    rtti->RegisterFunction(path);
    auto mset = RED4ext::CGlobalFunction::Create("HomesteadMouseSet", "HomesteadMouseSet", &MouseSetNative);
    mset->flags = flags;
    mset->AddParam("Bool", "on");
    mset->SetReturnType("Bool");
    rtti->RegisterFunction(mset);
    auto mx = RED4ext::CGlobalFunction::Create("HomesteadMouseX", "HomesteadMouseX", &MouseXNative);
    mx->flags = flags;
    mx->SetReturnType("Float");
    rtti->RegisterFunction(mx);
    auto my = RED4ext::CGlobalFunction::Create("HomesteadMouseY", "HomesteadMouseY", &MouseYNative);
    my->flags = flags;
    my->SetReturnType("Float");
    rtti->RegisterFunction(my);
    auto gk = RED4ext::CGlobalFunction::Create("HomesteadGameKeys", "HomesteadGameKeys", &GameKeysNative);
    gk->flags = flags;
    gk->SetReturnType("String");
    rtti->RegisterFunction(gk);
}

RED4EXT_C_EXPORT bool RED4EXT_CALL Main(RED4ext::v1::PluginHandle, RED4ext::v1::EMainReason aReason, const RED4ext::v1::Sdk*)
{
    if (aReason == RED4ext::v1::EMainReason::Load)
    {
        auto rtti = RED4ext::CRTTISystem::Get();
        rtti->AddRegisterCallback(RegisterTypes);
        rtti->AddPostRegisterCallback(PostRegisterTypes);
    }
    return true;
}

RED4EXT_C_EXPORT void RED4EXT_CALL Query(RED4ext::v1::PluginInfo* aInfo)
{
    aInfo->name = L"Homestead";
    aInfo->author = L"Homestead";
    aInfo->version = RED4EXT_V1_SEMVER(1, 0, 0);
    aInfo->runtime = RED4EXT_V1_RUNTIME_VERSION_INDEPENDENT;
    aInfo->sdk = RED4EXT_V1_SDK_VERSION_CURRENT;
}

RED4EXT_C_EXPORT uint32_t RED4EXT_CALL Supports() { return RED4EXT_API_VERSION_1; }
