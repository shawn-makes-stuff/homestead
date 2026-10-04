import Codeware.UI.*
@if(ModuleExists("Audioware"))
import Audioware.*
// Homestead: engine hooks for the CET mod (bin/x64/plugins/cyber_engine_tweaks/mods/Homestead).
// No module: CET only sees global classes. Lua observes the empty Homestead* methods.

public class HomesteadService extends ScriptableService {
    private let ui: ref<HomesteadUI>;
    public let fly: Bool;                                       // flying: mouse motion is reported too (Lua spaces its teleports)
    public let mouse: Bool;                                     // the gizmo's cursor is on: mouse motion goes to Lua

    public func UI() -> ref<HomesteadUI> {
        if !IsDefined(this.ui) { this.ui = new HomesteadUI(); }
        return this.ui;
    }

    private cb func OnLoad() {
        let cb = GameInstance.GetCallbackSystem();
        // our pieces all spawn from one empty template; Lua gives them their mesh and colliders here
        cb.RegisterCallback(n"Entity/Initialize", this, n"OnEntityInit")
            .AddTarget(EntityTarget.Template(r"homestead\\empty.ent"))
            .AddTarget(EntityTarget.Template(r"homestead\\empty_lit.ent"))
            .AddTarget(EntityTarget.Template(r"base\\gameplay\\devices\\stash\\stash.ent"));   // (a container's storage)
        cb.RegisterCallback(n"Input/Key", this, n"OnKey");
        cb.RegisterCallback(n"Input/Axis", this, n"OnAxis")
            .AddTarget(InputTarget.Axis(EInputKey.IK_MouseZ));
        cb.RegisterCallback(n"Session/Ready", this, n"OnSessionReady");
        cb.RegisterCallback(n"Session/BeforeEnd", this, n"OnSessionEnd");
    }

    private cb func OnSessionReady(event: ref<GameSessionEvent>) { this.HomesteadSession(true); }
    private cb func OnSessionEnd(event: ref<GameSessionEvent>) {
        if IsDefined(this.ui) { this.ui.Forget(); }
        this.HomesteadSession(false);
    }

    private cb func OnEntityInit(event: ref<EntityLifecycleEvent>) {
        this.HomesteadEntity(event.GetEntity());
    }

    private cb func OnKey(event: ref<KeyInputEvent>) {
        let act = event.GetAction();
        if NotEquals(act, EInputAction.IACT_Press) && NotEquals(act, EInputAction.IACT_Release) { return; }
        this.HomesteadKey(EnumValueToString("EInputKey", Cast<Int64>(EnumInt(event.GetKey()))), Equals(act, EInputAction.IACT_Press), event.IsShiftDown());
    }

    // the mouse wheel arrives as an axis: one "key press" per notch. The target above doesn't filter: mouse X/Y
    // arrive here too (and read as wheel notches, so looking down raised a free piece), so check the key.
    private cb func OnAxis(event: ref<AxisInputEvent>) {
        let k = event.GetKey();
        if Equals(k, EInputKey.IK_MouseX) { if this.mouse || this.fly { this.HomesteadMouse(event.GetValue(), 0.0); } return; }
        if Equals(k, EInputKey.IK_MouseY) { if this.mouse { this.HomesteadMouse(0.0, event.GetValue()); } return; }
        if NotEquals(k, EInputKey.IK_MouseZ) { return; }
        let v = event.GetValue();
        if v > 0.0 { this.HomesteadKey("IK_MouseWheelUp", true, event.IsShiftDown()); }
        if v < 0.0 { this.HomesteadKey("IK_MouseWheelDown", true, event.IsShiftDown()); }
    }

    public func HomesteadEntity(entity: wref<Entity>) {}
    public func HomesteadKey(key: String, down: Bool, shift: Bool) {}
    public func HomesteadMouse(dx: Float, dy: Float) {}
    public func HomesteadSession(start: Bool) {}
}

public abstract class Homestead {
    // First hit on the world (static meshes and terrain: the Badlands ground is only in Terrain) between two points:
    // XYZ = the point, W = 1; W = 0 when nothing is hit.
    public static func Ray(from: Vector4, to: Vector4) -> Vector4 {
        let filter: QueryFilter;
        QueryFilter.AddGroup(filter, n"Static");
        QueryFilter.AddGroup(filter, n"Terrain");
        let hit: TraceResult;
        if !GameInstance.GetSpatialQueriesSystem(GetGameInstance()).SyncRaycastByQueryFilter(from, to, filter, hit, false, false) {
            return new Vector4(0.0, 0.0, 0.0, 0.0);
        }
        return new Vector4(hit.position.X, hit.position.Y, hit.position.Z, 1.0);
    }

    // Ray() plus the surface normal: [point (W = 1 when hit), normal]
    public static func RayHit(from: Vector4, to: Vector4) -> array<Vector4> {
        let filter: QueryFilter;
        QueryFilter.AddGroup(filter, n"Static");
        QueryFilter.AddGroup(filter, n"Terrain");
        let hit: TraceResult;
        let out: array<Vector4>;
        if !GameInstance.GetSpatialQueriesSystem(GetGameInstance()).SyncRaycastByQueryFilter(from, to, filter, hit, false, false) {
            ArrayPush(out, new Vector4(0.0, 0.0, 0.0, 0.0));
            ArrayPush(out, new Vector4(0.0, 0.0, 1.0, 0.0));
            return out;
        }
        ArrayPush(out, new Vector4(hit.position.X, hit.position.Y, hit.position.Z, 1.0));
        ArrayPush(out, new Vector4(hit.normal.X, hit.normal.Y, hit.normal.Z, 0.0));
        return out;
    }

    // the terrain alone straight below a point (free placement's floor: nothing placed counts); Z, W = 1 when hit
    public static func TerrainBelow(at: Vector4) -> Vector4 {
        let filter: QueryFilter;
        QueryFilter.AddGroup(filter, n"Terrain");
        let hit: TraceResult;
        let from = new Vector4(at.X, at.Y, at.Z + 2.0, 1.0);
        let to = new Vector4(at.X, at.Y, at.Z - 80.0, 1.0);
        if !GameInstance.GetSpatialQueriesSystem(GetGameInstance()).SyncRaycastByQueryFilter(from, to, filter, hit, false, false) {
            return new Vector4(0.0, 0.0, 0.0, 0.0);
        }
        return new Vector4(hit.position.X, hit.position.Y, hit.position.Z, 1.0);
    }

    public static func CameraPos() -> Vector4 {
        let t: Transform;
        GameInstance.GetCameraSystem(GetGameInstance()).GetActiveCameraWorldTransform(t);
        return t.position;
    }

    // Build mode: no weapons, scanner, hacks, zoom or radial menus (GameplayRestriction.HomesteadBuild, r6/tweaks)
    public static func Restrict(on: Bool) {
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(player) { return; }
        if on {
            StatusEffectHelper.ApplyStatusEffect(player, t"GameplayRestriction.HomesteadBuild");
        } else {
            StatusEffectHelper.RemoveStatusEffect(player, t"GameplayRestriction.HomesteadBuild");
        }
    }

    // The free-placement gizmo: V held still and the mouse ours. With the plugin's mouse capture the camera gets no motion
    // (GameplayRestriction.HomesteadHold: no movement); without it the camera is restricted too (HomesteadGizmo: NoCameraControl, which drifts).
    // Returns whether the capture is on (Lua then reads the motion from HomesteadImport.MouseX / MouseY).
    public static func Fly(on: Bool) -> Void {
        let service = GameInstance.GetScriptableServiceContainer().GetService(n"HomesteadService") as HomesteadService;
        if IsDefined(service) { service.fly = on; }
    }

    public static func Gizmo(on: Bool) -> Bool {
        let service = GameInstance.GetScriptableServiceContainer().GetService(n"HomesteadService") as HomesteadService;
        if IsDefined(service) { service.mouse = on; }
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(player) { return false; }
        let captured = HomesteadImport.MouseSet(on);
        let effect = captured ? t"GameplayRestriction.HomesteadHold" : t"GameplayRestriction.HomesteadGizmo";
        if on { StatusEffectHelper.ApplyStatusEffect(player, effect); }
        else {
            StatusEffectHelper.RemoveStatusEffect(player, t"GameplayRestriction.HomesteadHold");
            StatusEffectHelper.RemoveStatusEffect(player, t"GameplayRestriction.HomesteadGizmo");
        }
        return captured;
    }

    // Phantom Liberty installed? (its characters are placeable only then)
    public static func HasEP1() -> Bool { return IsEP1(); }

    // for projecting the gizmo onto the screen: the screen in pixels and the camera's field of view (degrees)
    public static func ScreenSize() -> Vector2 { return ScreenHelper.GetScreenSize(GetGameInstance()); }
    public static func CameraFOV() -> Float {
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(player) { return 80.0; }
        return player.GetFPPCameraComponent().GetFOV();
    }

    // no damage to V (workshop mode: while falling, so a drop from a build doesn't hurt); on / off by source name
    public static func Unhurt(on: Bool) {
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(player) { return; }
        let god = GameInstance.GetGodModeSystem(GetGameInstance());
        if on { god.AddGodMode(player.GetEntityID(), gameGodModeType.Invulnerable, n"HomesteadFall"); }
        else { god.RemoveGodMode(player.GetEntityID(), gameGodModeType.Invulnerable, n"HomesteadFall"); }
    }

    // a game sound event, played on V (menu blips are 2D; the placing thuds sit at V's feet)
    public static func Sound(name: String) {
        let player = GetPlayer(GetGameInstance());
        if IsDefined(player) { GameObject.PlaySoundEvent(player, StringToName(name)); }
    }

    // A Fallout sound (tools/fo4/sounds.py: Audioware events) at a piece: played (looping or once) or stopped. False
    // when Audioware isn't installed: pieces are silent, nothing else changes.
    public static func Sfx(id: EntityID, ev: String, play: Bool, loop: Bool, vol: Float) -> Bool {
        return HomesteadSfx(id, StringToName(ev), play, loop, vol);
    }
    public static func SfxForget(id: EntityID) { HomesteadSfxForget(id); }

    // A hint in the game's own list (bottom right, with Draw Weapon and Crouch): its look, its order, and it moves
    // when the list does (a weapon drawn, a menu). The key comes from an input action (init.lua gameHints), so it follows the player's own bindings.
    public static func Hint(action: String, label: String, show: Bool, hold: Bool, order: Int32) {
        let data: InputHintData;
        data.action = StringToName(action);
        data.source = n"Homestead";
        data.localizedLabel = label;
        data.enableHoldAnimation = hold;
        data.sortingPriority = order;
        let evt = new UpdateInputHintEvent();
        evt.data = data;
        evt.show = show;
        evt.targetHintContainer = n"GameplayInputHelper";
        GameInstance.GetUISystem(GetGameInstance()).QueueEvent(evt);
    }

    public static func InMenu() -> Bool {
        let game = GetGameInstance();
        let ui = GameInstance.GetBlackboardSystem(game).Get(GetAllBlackboardDefs().UI_System);
        return ui.GetBool(GetAllBlackboardDefs().UI_System.IsInMenu) || GameInstance.GetTimeSystem(game).IsPausedState();
    }

    // People walk on the game's navmesh, which LiveNav (optional) makes hold our pieces (modules/livenav.lua). The
    // nearest point on the human navmesh within r of (x, y, z): XYZ the point (Z onto the surface just under it: the
    // navmesh floats a little), W = 1; W = 0 none within r, W = -1 not streamed in there (unknown, not "no")
    public static func NavPoint(x: Float, y: Float, z: Float, r: Float) -> Vector4 {
        let nav = GameInstance.GetNavigationSystem(GetGameInstance());
        let at = new Vector4(x, y, z, 1.0);
        if !nav.IsNavmeshStreamedInLocation(at, r) { return new Vector4(x, y, z, -1.0); }
        let res = nav.FindPointInSphereOnlyHumanNavmesh(at, r, NavGenAgentSize.Human, true);
        if NotEquals(res.status, worldNavigationRequestStatus.OK) { return new Vector4(x, y, z, 0.0); }
        let p = res.point;
        let filter: QueryFilter;
        QueryFilter.AddGroup(filter, n"Static");
        QueryFilter.AddGroup(filter, n"Terrain");
        let hit: TraceResult;
        let top = p.Z;
        if GameInstance.GetSpatialQueriesSystem(GetGameInstance()).SyncRaycastByQueryFilter(new Vector4(p.X, p.Y, p.Z + 0.15, 1.0), new Vector4(p.X, p.Y, p.Z - 0.4, 1.0), filter, hit, false, false) {
            top = hit.position.Z;
        }
        return new Vector4(p.X, p.Y, top, 1.0);
    }
    // the game's own path between two points on its navmesh (corners), empty when there's none
    public static func NavPath(a: Vector4, b: Vector4) -> array<Vector4> {
        let out: array<Vector4>;
        let p = GameInstance.GetNavigationSystem(GetGameInstance()).CalculatePathOnlyHumanNavmesh(a, b, NavGenAgentSize.Human, 1.0);
        if IsDefined(p) { out = p.path; }
        return out;
    }
}

// Workshop mode: right mouse turns pieces, so it must not also raise V's aim (unarmed, that zooms the camera in).
// GameplayRestriction.HomesteadBuild carries the tag.
@wrapMethod(AimingStateDecisions)
protected const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
    if StatusEffectSystem.ObjectHasStatusEffectWithTag(scriptInterface.executionOwner, n"HomesteadBuild") { return false; }
    return wrappedMethod(stateContext, scriptInterface);
}

// E (the game's iconic cyberware key) places and grabs pieces: no Berserk / Sandevistan / Overclock from it while building
@wrapMethod(PlayerPuppet)
private final func ActivateIconicCyberware() {
    if StatusEffectSystem.ObjectHasStatusEffectWithTag(this, n"HomesteadBuild") { return; }
    wrappedMethod();
}

// (Audioware optional: compiled against it only when it's there)
@if(ModuleExists("Audioware"))
func HomesteadSfx(id: EntityID, ev: CName, play: Bool, loop: Bool, vol: Float) -> Bool {
    let a = GameInstance.GetAudioSystemExt(GetGameInstance());
    if !play { a.StopOnEmitter(ev, id, n"hs"); return true; }
    if !a.IsRegisteredEmitter(id, n"hs") && !a.RegisterEmitter(id, n"hs", n"Homestead") { return false; }
    let s = new AudioSettingsExt();
    s.loop = loop;
    s.volume = vol;
    a.PlayOnEmitter(ev, id, n"hs", s);
    return true;
}
@if(ModuleExists("Audioware"))
func HomesteadSfxForget(id: EntityID) {
    let a = GameInstance.GetAudioSystemExt(GetGameInstance());
    if a.IsRegisteredEmitter(id, n"hs") { a.UnregisterEmitter(id, n"hs"); }
}
@if(!ModuleExists("Audioware"))
func HomesteadSfx(id: EntityID, ev: CName, play: Bool, loop: Bool, vol: Float) -> Bool { return false; }
@if(!ModuleExists("Audioware"))
func HomesteadSfxForget(id: EntityID) {}
