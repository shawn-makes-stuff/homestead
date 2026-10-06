import Codeware.UI.*
@if(ModuleExists("Audioware"))
import Audioware.*
// Homestead: engine hooks for the CET mod (bin/x64/plugins/cyber_engine_tweaks/mods/Homestead).
// No module: CET only sees global classes. Lua observes the empty Homestead* methods.

public class HomesteadService extends ScriptableService {
    private let ui: ref<HomesteadUI>;
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
        cb.RegisterCallback(n"Session/BeforeSave", this, n"OnSave");   // (modules/world.lua: our pieces' file is this save's)
    }

    private cb func OnSessionReady(event: ref<GameSessionEvent>) { this.HomesteadSession(true); }
    private cb func OnSessionEnd(event: ref<GameSessionEvent>) {
        if IsDefined(this.ui) { this.ui.Forget(); }
        this.HomesteadSession(false);
    }

    private cb func OnSave(event: ref<GameSessionEvent>) { this.HomesteadSaved(); }

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
        if Equals(k, EInputKey.IK_MouseX) { if this.mouse { this.HomesteadMouse(event.GetValue(), 0.0); } return; }
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
    public func HomesteadSaved() {}
}

public abstract class Homestead {
    // the first hit between two points on the terrain, and with statics on the static meshes too
    private static func Trace(from: Vector4, to: Vector4, statics: Bool, out hit: TraceResult) -> Bool {
        let filter: QueryFilter;
        if statics { QueryFilter.AddGroup(filter, n"Static"); }
        QueryFilter.AddGroup(filter, n"Terrain");
        return GameInstance.GetSpatialQueriesSystem(GetGameInstance()).SyncRaycastByQueryFilter(from, to, filter, hit, false, false);
    }

    // First hit on the world (static meshes and terrain: the Badlands ground is only in Terrain) between two points:
    // XYZ = the point, W = 1; W = 0 when nothing is hit.
    public static func Ray(from: Vector4, to: Vector4) -> Vector4 {
        let hit: TraceResult;
        if !Homestead.Trace(from, to, true, hit) { return new Vector4(0.0, 0.0, 0.0, 0.0); }
        return new Vector4(hit.position.X, hit.position.Y, hit.position.Z, 1.0);
    }

    // Ray() plus the surface normal: [point (W = 1 when hit), normal]
    public static func RayHit(from: Vector4, to: Vector4) -> array<Vector4> {
        let hit: TraceResult;
        let out: array<Vector4>;
        if !Homestead.Trace(from, to, true, hit) {
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
        let hit: TraceResult;
        if !Homestead.Trace(new Vector4(at.X, at.Y, at.Z + 2.0, 1.0), new Vector4(at.X, at.Y, at.Z - 80.0, 1.0), false, hit) {
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

    // Turrets (modules/turret.lua). Who is attacking V: on V's own list of hostile threats, alive, hostile to V and
    // in combat. Police that aren't after V are none of these.
    public static func Attackers() -> array<ref<NPCPuppet>> {
        let out: array<ref<NPCPuppet>>;
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(player) || !IsDefined(player.GetTargetTrackerComponent()) { return out; }
        let threats = player.GetTargetTrackerComponent().GetHostileThreats(false);
        for t in threats {
            let npc = t.entity as NPCPuppet;
            if IsDefined(npc) && ScriptedPuppet.IsActive(npc) && NPCPuppet.IsInCombat(npc)
                && Equals(GameObject.GetAttitudeTowards(npc, player), EAIAttitude.AIA_Hostile) {
                ArrayPush(out, npc);
            }
        }
        return out;
    }

    // A turret's hit: a percentage of the target's health, as V's doing
    public static func TurretHit(npc: ref<NPCPuppet>, percent: Float) {
        let player = GetPlayer(GetGameInstance());
        if !IsDefined(npc) || !IsDefined(player) { return; }
        GameInstance.GetStatPoolsSystem(GetGameInstance()).RequestChangingStatPoolValue(Cast<StatsObjectID>(npc.GetEntityID()), gamedataStatPoolType.Health, -percent, player, false, true);
    }

    // An entity's identity for what is kept about it across saves (modules/life.lua jobs): its tag "hsu:<uid>" -> the uid,
    // "" if it has none. Entity ids are a session's: a load gives every piece a new one (seen 2026-10-05: jobs kept by
    // id matched nobody after a load).
    public static func Uid(id: EntityID) -> String {
        let tags = GameInstance.GetDynamicEntitySystem().GetTags(id);
        for tag in tags {
            let text = NameToString(tag);
            if StrBeginsWith(text, "hsu:") { return StrMid(text, 4); }
        }
        return "";
    }

    // A person moved the way their AI moves them (a teleport command: what Appearance Menu Mod moves people by - the
    // teleportation facility alone left ours where they were under the gizmo, user 2026-10-05). Not a person: nothing.
    public static func MoveNPC(e: ref<Entity>, at: Vector4, yaw: Float) {
        let npc = e as NPCPuppet;
        if !IsDefined(npc) || !IsDefined(npc.GetAIControllerComponent()) { return; }
        let cmd = new AITeleportCommand();
        cmd.position = at;
        cmd.rotation = yaw;
        cmd.doNavTest = false;
        npc.GetAIControllerComponent().SendCommand(cmd);
    }

    // the import notice (below), for init.lua: shown; its closing is OnHomesteadNoticeClosed, watched there
    public static func Notice(menu: ref<SingleplayerMenuGameController>, title: String, text: String) {
        if IsDefined(menu) { menu.HomesteadNotice(title, text); }
    }

    // The game's own hand cursor, as over its terminals and elevator panels (an elevator's buttons: modules/elevator.lua).
    // It is the HUD's (cursor_device.script: shown while UIGameData.InteractionData says a terminal is being used - the
    // crosshair goes, and a click doesn't fire). Written only when it differs: the game writes it too.
    public static func Hand(on: Bool) {
        let bb = GameInstance.GetBlackboardSystem(GetGameInstance()).Get(GetAllBlackboardDefs().UIGameData);
        if !IsDefined(bb) { return; }
        let data: bbUIInteractionData;
        let v = bb.GetVariant(GetAllBlackboardDefs().UIGameData.InteractionData);
        if IsDefined(v) { data = FromVariant<bbUIInteractionData>(v); }
        if Equals(data.terminalInteractionActive, on) { return; }
        data.terminalInteractionActive = on;
        bb.SetVariant(GetAllBlackboardDefs().UIGameData.InteractionData, ToVariant(data), true);
    }

    // a game sound event at one of our pieces (a turret's shot)
    public static func SoundAt(id: EntityID, name: String) {
        let obj = GameInstance.FindEntityByID(GetGameInstance(), id) as GameObject;
        if IsDefined(obj) { GameObject.PlaySoundEvent(obj, StringToName(name)); }
    }

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
        let hit: TraceResult;
        if Homestead.Trace(new Vector4(p.X, p.Y, p.Z + 0.15, 1.0), new Vector4(p.X, p.Y, p.Z - 0.4, 1.0), true, hit) { p.Z = hit.position.Z; }
        return new Vector4(p.X, p.Y, p.Z, 1.0);
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

// The import notice on the main menu (init.lua): the game's own message box. Its token is let go when the box closes -
// held on, the box's layer stays over the menu and takes every click.
@addField(SingleplayerMenuGameController)
private let hsNotice: ref<inkGameNotificationToken>;

@addMethod(SingleplayerMenuGameController)
public func HomesteadNotice(title: String, text: String) {
    this.hsNotice = GenericMessageNotification.Show(this, title, text, GenericMessageNotificationType.OK);
    this.hsNotice.RegisterListener(this, n"OnHomesteadNoticeClosed");
}

@addMethod(SingleplayerMenuGameController)
protected cb func OnHomesteadNoticeClosed(data: ref<inkGameNotificationData>) -> Bool {
    this.hsNotice = null;
}
