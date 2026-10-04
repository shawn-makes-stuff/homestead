import Codeware.UI.*

// Homestead's on-screen UI in native ink widgets (Codeware): Fallout 4's workshop layout in the game's own style
// (salmon-red labels, cyan selection, cyan outlined key boxes, orange accent bars, dark translucent slots).
// Resolution: everything is designed in 3840 x 2160 units on a "stage" canvas, scaled by
// min(screen W / 3840, screen H / 2160) (Codeware's VirtualResolution rule) and sized to cover the whole screen, so
// anchors at the stage's edges and centre work at any resolution and aspect ratio. The HUD layer itself is in pixels.
// Text is positioned by its pivot (anchor point), with fit-to-content sizes: the text alignment setting is ignored
// by the game.
// Lua calls HomesteadUI.Render(...) only when something changed; it rebuilds the whole overlay.

public class HomesteadUI {
    private let root: wref<inkCanvas>;

    public static func Red() -> HDRColor { return new HDRColor(1.1761, 0.3809, 0.3476, 1.0); }
    public static func DimRed() -> HDRColor { return new HDRColor(0.58, 0.2, 0.19, 1.0); }
    public static func Cyan() -> HDRColor { return new HDRColor(0.3686, 0.9647, 1.0, 1.0); }
    public static func DimCyan() -> HDRColor { return new HDRColor(0.16, 0.42, 0.45, 1.0); }
    public static func Orange() -> HDRColor { return new HDRColor(1.0, 0.56, 0.12, 1.0); }
    public static func Yellow() -> HDRColor { return new HDRColor(1.0, 0.87, 0.3, 1.0); }
    public static func Pale() -> HDRColor { return new HDRColor(0.82, 0.84, 0.84, 1.0); }
    public static func Dark() -> HDRColor { return new HDRColor(0.035, 0.022, 0.03, 1.0); }

    public func Forget() { this.root = null; this.gizmo = null; this.usePane = null; this.targetPane = null; ArrayClear(this.segs); }

    private static func Instance() -> ref<HomesteadUI> {
        let s = GameInstance.GetScriptableServiceContainer().GetService(n"HomesteadService") as HomesteadService;
        return s.UI();
    }

    private func Root() -> ref<inkCanvas> {
        if IsDefined(this.root) { return this.root; }
        let layer = GameInstance.GetInkSystem().GetLayer(n"inkHUDLayer");
        if !IsDefined(layer) || !IsDefined(layer.GetVirtualWindow()) { return null; }
        let root = new inkCanvas();
        root.SetName(n"Homestead");
        root.SetAnchor(inkEAnchor.Fill);
        root.Reparent(layer.GetVirtualWindow());
        this.root = root;
        return root;
    }

    // the scaled 3840 x 2160-unit stage covering the screen
    private static func Stage(root: wref<inkCompoundWidget>) -> ref<inkCanvas> {
        let screen = ScreenHelper.GetScreenSize(GetGameInstance());
        if screen.X < 1.0 || screen.Y < 1.0 { screen = new Vector2(3840.0, 2160.0); }
        let s = MinF(screen.X / 3840.0, screen.Y / 2160.0);
        let stage = new inkCanvas();
        stage.SetAnchor(inkEAnchor.Centered);
        stage.SetAnchorPoint(0.5, 0.5);
        stage.SetSize(screen.X / s, screen.Y / s);
        stage.SetRenderTransformPivot(0.5, 0.5);
        stage.SetScale(new Vector2(s, s));
        stage.Reparent(root);
        return stage;
    }

    // a stage of its own on the HUD layer (the menu's root is cleared by every Render: what lives apart - the gizmo,
    // the use prompt, the target's name - can't sit on it), or null before the layer is up
    private static func Layer(name: CName) -> ref<inkCanvas> {
        let layer = GameInstance.GetInkSystem().GetLayer(n"inkHUDLayer");
        if !IsDefined(layer) || !IsDefined(layer.GetVirtualWindow()) { return null; }
        let c = HomesteadUI.Stage(layer.GetVirtualWindow());
        c.SetName(name);
        return c;
    }


    private static func Box(parent: ref<inkCanvas>, anchor: inkEAnchor, px: Float, py: Float, x: Float, y: Float, w: Float, h: Float) -> ref<inkCanvas> {
        let c = new inkCanvas();
        c.SetAnchor(anchor);
        c.SetAnchorPoint(px, py);
        c.SetSize(w, h);
        c.SetTranslation(x, y);
        c.Reparent(parent);
        return c;
    }

    private static func Rect(parent: ref<inkCanvas>, x: Float, y: Float, w: Float, h: Float, color: HDRColor, opacity: Float) {
        let r = new inkRectangle();
        r.SetAnchor(inkEAnchor.TopLeft);
        r.SetSize(w, h);
        r.SetTranslation(x, y);
        r.SetTintColor(color);
        r.SetOpacity(opacity);
        r.Reparent(parent);
    }

    private static func Frame(parent: ref<inkCanvas>, x: Float, y: Float, w: Float, h: Float, t: Float, color: HDRColor, opacity: Float) {
        HomesteadUI.Rect(parent, x, y, w, t, color, opacity);
        HomesteadUI.Rect(parent, x, y + h - t, w, t, color, opacity);
        HomesteadUI.Rect(parent, x, y + t, t, h - 2.0 * t, color, opacity);
        HomesteadUI.Rect(parent, x + w - t, y + t, t, h - 2.0 * t, color, opacity);
    }

    private static func Text(parent: ref<inkCanvas>, x: Float, y: Float, px: Float, py: Float, text: String, size: Int32,
                             color: HDRColor, style: CName) {
        let t = new inkText();
        t.SetAnchor(inkEAnchor.TopLeft);
        t.SetAnchorPoint(px, py);
        t.SetFitToContent(true);
        t.SetTranslation(x, y);
        t.SetFontFamily("base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily");
        t.SetFontStyle(style);
        t.SetFontSize(size);
        t.SetLetterCase(textLetterCase.UpperCase);
        t.SetTintColor(color);
        t.SetText(text);
        t.Reparent(parent);
    }

    public static func KeyWidth(key: String) -> Float {
        let n = Cast<Float>(StrLen(key));
        return n <= 1.0 ? 58.0 : 30.0 + 21.0 * n;
    }

    private static func Key(parent: ref<inkCanvas>, x: Float, y: Float, key: String) {
        let w = HomesteadUI.KeyWidth(key);
        let h = 58.0;
        HomesteadUI.Rect(parent, x, y - h / 2.0, w, h, HomesteadUI.Dark(), 0.55);
        HomesteadUI.Frame(parent, x, y - h / 2.0, w, h, 3.0, HomesteadUI.Cyan(), 1.0);
        HomesteadUI.Text(parent, x + w / 2.0, y + 1.0, 0.5, 0.5, key, 36, HomesteadUI.Cyan(), n"Semi-Bold");
    }


    // prompt: at the workbench. build: the workshop menu is up; level 0 = category tabs focused, 1 = the category's
    // groups, 2 = the group's items (one is held). names/thumbs: the cards in the row (groups at levels 0-1, items at
    // 2), thumbs[k] a folder's item count ("" for an item). CET can pass at most 15 arguments: keep it at 15;
    // item: the selected card; detail: a line about it. crumb: where the menu is. key: the workshop key's name (the
    // prompt's key box: it follows a rebind). (The hints: the game's own list, Homestead.Hint.)
    public static func Render(prompt: Bool, build: Bool, level: Int32, cats: array<String>, cat: Int32, crumb: String,
                              names: array<String>, thumbs: array<String>, item: Int32, detail: String, count: Int32, budget: Int32,
                              key: String, toast: String) {
        let ui = HomesteadUI.Instance();
        if !IsDefined(ui) { return; }
        let root = ui.Root();
        if !IsDefined(root) { return; }
        root.RemoveAllChildren();
        let stage = HomesteadUI.Stage(root);

        if prompt {
            let p = HomesteadUI.Box(stage, inkEAnchor.Centered, 0.0, 0.5, 190.0, 40.0, 700.0, 130.0);
            HomesteadUI.Rect(p, 0.0, 8.0, 6.0, 114.0, HomesteadUI.Red(), 1.0);
            HomesteadUI.Text(p, 26.0, 34.0, 0.0, 0.5, "Workbench", 32, HomesteadUI.Red(), n"Medium");
            HomesteadUI.Key(p, 26.0, 90.0, key);
            HomesteadUI.Text(p, 26.0 + HomesteadUI.KeyWidth(key) + 18.0, 90.0, 0.0, 0.5, "Workshop", 44, HomesteadUI.Cyan(), n"Semi-Bold");
        }

        if build {
            let dot = HomesteadUI.Box(stage, inkEAnchor.Centered, 0.5, 0.5, 0.0, 0.0, 14.0, 14.0);
            HomesteadUI.Rect(dot, 0.0, 0.0, 14.0, 14.0, HomesteadUI.Dark(), 0.6);
            HomesteadUI.Rect(dot, 3.0, 3.0, 8.0, 8.0, HomesteadUI.Cyan(), 1.0);

            let cw = 300.0;
            let ch = 270.0;
            let gap = 20.0;
            let W = 5.0 * cw + 4.0 * gap;
            let top = 176.0;
            let m = HomesteadUI.Box(stage, inkEAnchor.TopCenter, 0.5, 0.0, 0.0, 80.0, W, 560.0);
            HomesteadUI.Text(m, 0.0, 26.0, 0.0, 0.5, crumb, 36, HomesteadUI.Red(), n"Semi-Bold");
            HomesteadUI.Text(m, W, 26.0, 1.0, 0.5, "Size  " + IntToString(count * 100 / Max(budget, 1)) + "%", 32,
                             HomesteadUI.Red(), n"Medium");
            let bw = 360.0;
            let fill = bw * MinF(1.0, Cast<Float>(count) / Cast<Float>(Max(budget, 1)));
            HomesteadUI.Rect(m, W - bw, 52.0, bw, 5.0, HomesteadUI.DimRed(), 0.8);
            HomesteadUI.Rect(m, W - bw, 52.0, fill, 5.0, HomesteadUI.Red(), 1.0);
            HomesteadUI.Rect(m, 0.0, 66.0, W, 2.0, HomesteadUI.Red(), 0.45);

            let n = ArraySize(cats);
            let tabW = 316.0;
            let t = -2;
            while t <= 2 {
                let i = cat + t;
                if i >= 0 && i < n {
                    let sel = t == 0;
                    let tx = W / 2.0 + Cast<Float>(t) * tabW;
                    HomesteadUI.Text(m, tx, 112.0, 0.5, 0.5, cats[i], sel ? 40 : 34, sel ? HomesteadUI.Cyan() : HomesteadUI.Red(),
                                     sel ? n"Semi-Bold" : n"Medium");
                    if sel {
                        HomesteadUI.Rect(m, tx - 100.0, 142.0, 200.0, 4.0, level == 0 ? HomesteadUI.Cyan() : HomesteadUI.DimCyan(), 1.0);
                    }
                }
                t += 1;
            }
            if cat > 2 { HomesteadUI.Text(m, -26.0, 112.0, 1.0, 0.5, "<", 40, HomesteadUI.Red(), n"Semi-Bold"); }
            if cat + 2 < n - 1 { HomesteadUI.Text(m, W + 26.0, 112.0, 0.0, 0.5, ">", 40, HomesteadUI.Red(), n"Semi-Bold"); }

            let total = ArraySize(names);
            let d = -2;
            while d <= 2 {
                let k = item + d;
                if k >= 0 && k < total {
                    let sel = d == 0;
                    let focus = sel && level > 0;
                    let cx = W / 2.0 - cw / 2.0 + Cast<Float>(d) * (cw + gap);
                    let folder = k < ArraySize(thumbs) && NotEquals(thumbs[k], "") && StrFindFirst(thumbs[k], "|") < 0;
                    let edge = focus ? HomesteadUI.Cyan() : (sel ? HomesteadUI.Red() : HomesteadUI.DimRed());
                    if folder {
                        HomesteadUI.Rect(m, cx + 12.0, top - 12.0, cw, ch, HomesteadUI.Dark(), 0.6);
                        HomesteadUI.Frame(m, cx + 12.0, top - 12.0, cw, ch, 2.0, edge, 0.35);
                        HomesteadUI.Rect(m, cx, top - 16.0, 120.0, 16.0, edge, focus ? 1.0 : 0.7);
                    }
                    HomesteadUI.Rect(m, cx, top, cw, ch, HomesteadUI.Dark(), 0.75);
                    if focus {
                        HomesteadUI.Frame(m, cx, top, cw, ch, 3.0, HomesteadUI.Cyan(), 1.0);
                    } else {
                        HomesteadUI.Frame(m, cx, top, cw, ch, 2.0, sel ? HomesteadUI.Red() : HomesteadUI.DimRed(), sel ? 0.9 : 0.55);
                    }
                    if !folder && k < ArraySize(thumbs) && StrFindFirst(thumbs[k], "|") >= 0 {
                        let at = StrSplit(thumbs[k], "|");
                        let im = new inkImage();
                        im.SetAtlasResource(HomesteadAtlas.Path(at[0]));
                        im.SetTexturePart(StringToName(at[1]));
                        im.SetAnchor(inkEAnchor.TopLeft);
                        im.SetSize(200.0, 200.0);
                        im.SetTranslation(cx + 50.0, top + 10.0);
                        im.SetOpacity(sel ? 1.0 : 0.85);
                        im.Reparent(m);
                    }
                    if folder {
                        HomesteadUI.Rect(m, cx + 85.0, top + 58.0, 52.0, 18.0, edge, 0.85);
                        HomesteadUI.Rect(m, cx + 85.0, top + 74.0, 130.0, 92.0, edge, 0.85);
                        HomesteadUI.Rect(m, cx + 85.0, top + 86.0, 130.0, 3.0, HomesteadUI.Dark(), 0.5);
                    }
                    HomesteadUI.Text(m, cx + cw / 2.0, top + ch - 34.0, 0.5, 0.5, names[k], StrLen(names[k]) > 20 ? 22 : (StrLen(names[k]) > 14 ? 27 : 32),
                                     focus ? HomesteadUI.Cyan() : (sel ? HomesteadUI.Pale() : HomesteadUI.Red()),
                                     sel ? n"Semi-Bold" : n"Medium");
                }
                d += 1;
            }
            if item > 2 { HomesteadUI.Text(m, -26.0, top + ch / 2.0, 1.0, 0.5, "<", 48, HomesteadUI.Red(), n"Semi-Bold"); }
            if item + 2 < total - 1 { HomesteadUI.Text(m, W + 26.0, top + ch / 2.0, 0.0, 0.5, ">", 48, HomesteadUI.Red(), n"Semi-Bold"); }
            if NotEquals(detail, "") {
                HomesteadUI.Text(m, W / 2.0, top + ch + 34.0, 0.5, 0.5, detail, 30, HomesteadUI.DimRed(), n"Medium");
            }
            if NotEquals(toast, "") {
                HomesteadUI.Text(m, W / 2.0, top + ch + 86.0, 0.5, 0.5, toast, 36, HomesteadUI.Yellow(), n"Semi-Bold");
            }

        }

    }

    private let targetPane: wref<inkCanvas>;
    private let targetText: wref<inkText>;
    public static func Target(name: String) {
        let ui = HomesteadUI.Instance();
        if !IsDefined(ui) { return; }
        if !IsDefined(ui.targetPane) {
            let stage = HomesteadUI.Layer(n"HomesteadTarget");
            if !IsDefined(stage) { return; }
            let t = HomesteadUI.Box(stage, inkEAnchor.Centered, 0.0, 0.5, 70.0, -70.0, 1000.0, 80.0);
            let tx = new inkText();
            tx.SetAnchor(inkEAnchor.TopLeft);
            tx.SetAnchorPoint(0.0, 0.5);
            tx.SetFitToContent(true);
            tx.SetTranslation(0.0, 40.0);
            tx.SetFontFamily("base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily");
            tx.SetFontStyle(n"Semi-Bold");
            tx.SetFontSize(38);
            tx.SetLetterCase(textLetterCase.UpperCase);
            tx.SetTintColor(HomesteadUI.Cyan());
            tx.Reparent(t);
            ui.targetPane = stage;
            ui.targetText = tx;
        }
        ui.targetText.SetText(name);
        ui.targetPane.SetVisible(NotEquals(name, ""));
    }



    private let gizmo: wref<inkCanvas>;
    private let usePane: wref<inkHorizontalPanel>;
    private let useKey: wref<inkImage>;
    private let useText: wref<inkText>;
    private let segs: array<wref<inkRectangle>>;
    private let cursor: wref<inkCanvas>;

    private func GizmoRoot() -> ref<inkCanvas> {
        if IsDefined(this.gizmo) { return this.gizmo; }
        let c = HomesteadUI.Layer(n"HomesteadGizmo");
        if !IsDefined(c) { return null; }
        this.gizmo = c;
        ArrayClear(this.segs);
        let k = new inkCanvas();                                 // the game's own mouse pointer: its arrow, filled and
        k.SetAnchor(inkEAnchor.TopLeft);                         // outlined (cursor_inventory's mouse_fill / mouse_frame;
        k.SetAnchorPoint(0.0, 0.0);                              // def_frame was its square selection frame: a white box),
        k.SetSize(62.0, 58.0);                                   // its tip on the point
        let parts = [n"mouse_fill", n"mouse_frame"];
        let i = 0;
        for part in parts {
            let im = new inkImage();
            im.SetAtlasResource(r"base\\gameplay\\gui\\widgets\\cursors\\cursor_inventory.inkatlas");
            im.SetTexturePart(part);
            im.SetAnchor(inkEAnchor.Fill);
            im.SetTintColor(HomesteadUI.Red());
            im.SetOpacity(i == 0 ? 0.35 : 1.0);
            im.Reparent(k);
            i += 1;
        }
        k.Reparent(c);
        this.cursor = k;
        return c;
    }

    private static func SegColor(i: Int32) -> HDRColor {
        switch i {
            case 0: return new HDRColor(1.2, 0.25, 0.22, 1.0);
            case 1: return new HDRColor(0.35, 1.1, 0.35, 1.0);
            case 2: return new HDRColor(0.3, 0.55, 1.3, 1.0);
            case 3: return HomesteadUI.Yellow();
            case 5: return HomesteadUI.Cyan();
        }
        return HomesteadUI.Pale();
    }

    // segs: x1, y1, x2, y2, colour, thickness per segment, positions 0..1 across the screen (from the top left);
    // label: a line under the cursor (what is grabbed, the offset and angles). An empty segs hides it all.
    public static func Gizmo(segs: array<Float>, cx: Float, cy: Float, label: String) {
        let ui = HomesteadUI.Instance();
        if !IsDefined(ui) { return; }
        if ArraySize(segs) == 0 {
            if IsDefined(ui.gizmo) { ui.gizmo.SetVisible(false); }
            return;
        }
        let c = ui.GizmoRoot();
        if !IsDefined(c) { return; }
        c.SetVisible(true);
        let W = c.GetWidth();
        let H = c.GetHeight();
        let n = ArraySize(segs) / 6;
        let i = 0;
        while i < n {
            if i >= ArraySize(ui.segs) {
                let r = new inkRectangle();
                r.SetAnchor(inkEAnchor.TopLeft);
                r.SetAnchorPoint(0.0, 0.5);
                r.SetRenderTransformPivot(0.0, 0.5);
                r.Reparent(c);
                ArrayPush(ui.segs, r);
            }
            let r = ui.segs[i];
            let x1 = segs[6 * i] * W;
            let y1 = segs[6 * i + 1] * H;
            let dx = segs[6 * i + 2] * W - x1;
            let dy = segs[6 * i + 3] * H - y1;
            r.SetSize(SqrtF(dx * dx + dy * dy) + 1.0, segs[6 * i + 5]);
            r.SetTranslation(x1, y1);
            r.SetRotation(Rad2Deg(AtanF(dy, dx)));
            r.SetTintColor(HomesteadUI.SegColor(Cast<Int32>(segs[6 * i + 4])));
            r.SetVisible(true);
            i += 1;
        }
        while i < ArraySize(ui.segs) { ui.segs[i].SetVisible(false); i += 1; }
        ui.cursor.SetVisible(cx >= 0.0);
        ui.cursor.SetTranslation(cx * W, cy * H);
        ui.cursor.Reparent(c);
    }

    // What the use key does to the piece V looks at, on the piece (x, y: its point on the screen, 0..1 from the top
    // left), as the game marks the things it lets V use: the key's own icon (key: its name, "F"; a key with a longer
    // name - no icon known for it - in brackets before the action), the action beside it. show false: gone.
    public static func Use(show: Bool, x: Float, y: Float, label: String, key: String) {
        let ui = HomesteadUI.Instance();
        if !IsDefined(ui) { return; }
        if !show {
            if IsDefined(ui.usePane) { ui.usePane.SetVisible(false); }
            return;
        }
        if !IsDefined(ui.usePane) {
            let c = HomesteadUI.Layer(n"HomesteadUse");
            if !IsDefined(c) { return; }
            let pane = new inkHorizontalPanel();
            pane.SetAnchor(inkEAnchor.TopLeft);
            pane.SetAnchorPoint(0.5, 0.5);
            pane.SetFitToContent(true);
            pane.Reparent(c);
            let key = new inkImage();
            key.SetAtlasResource(r"base\\gameplay\\gui\\common\\input\\icons_keyboard.inkatlas");
            key.SetSize(64.0, 64.0);
            key.SetVAlign(inkEVerticalAlign.Center);
            key.SetMargin(new inkMargin(0.0, 0.0, 16.0, 0.0));
            key.SetTintColor(HomesteadUI.Cyan());
            key.Reparent(pane);
            let t = new inkText();
            t.SetFitToContent(true);
            t.SetVAlign(inkEVerticalAlign.Center);
            t.SetFontFamily("base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily");
            t.SetFontStyle(n"Medium");
            t.SetFontSize(42);
            t.SetTintColor(HomesteadUI.Cyan());
            t.Reparent(pane);
            ui.usePane = pane;
            ui.useKey = key;
            ui.useText = t;
        }
        let letter = StrLen(key) == 1;
        if letter { ui.useKey.SetTexturePart(StringToName("kb_" + StrLower(key))); }
        ui.useKey.SetVisible(letter);
        let root = ui.usePane.GetParentWidget();
        ui.usePane.SetTranslation(x * root.GetWidth(), y * root.GetHeight());
        ui.useText.SetText(letter ? label : "[" + key + "]  " + label);
        ui.usePane.SetVisible(true);
    }
}
