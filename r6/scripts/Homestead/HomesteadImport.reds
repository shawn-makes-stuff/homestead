// The importer, started from the game (red4ext/plugins/Homestead/Homestead.dll: CET's Lua can't start programs).
// Lua calls HomesteadImport.Start(mode: 0 import, 1 fresh, 2 find the games) / Running() / Stop() / Path(); the import's progress is in the CET mod's import_status.txt.

public static native func HomesteadImportStart(mode: Int32) -> Bool
public static native func HomesteadImportRunning() -> Bool
public static native func HomesteadImportStop() -> Bool
public static native func HomesteadImportPath() -> String
// the gizmo's mouse: while on, the game's window gets no mouse motion (the camera stays, no restriction on it);
// MouseX / MouseY give the motion since last asked, for our cursor
public static native func HomesteadMouseSet(on: Bool) -> Bool
public static native func HomesteadMouseX() -> Float
public static native func HomesteadMouseY() -> Float
// the game's own key bindings live on foot, "action|IK_key" lines (the player's rebinds applied): Homestead's key
// settings say what else a key does, and the hints borrow the action for the key's icon
public static native func HomesteadGameKeys() -> String

public abstract class HomesteadImport {
    public static func GameKeys() -> String { return HomesteadGameKeys(); }
    public static func Start(mode: Int32) -> Bool { return HomesteadImportStart(mode); }
    public static func Running() -> Bool { return HomesteadImportRunning(); }
    public static func Stop() -> Bool { return HomesteadImportStop(); }
    public static func Path() -> String { return HomesteadImportPath(); }
    public static func MouseSet(on: Bool) -> Bool { return HomesteadMouseSet(on); }
    public static func MouseX() -> Float { return HomesteadMouseX(); }
    public static func MouseY() -> Float { return HomesteadMouseY(); }
}
