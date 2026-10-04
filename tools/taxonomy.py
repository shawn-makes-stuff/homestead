"""The menu's folder paths below each tab, from an item's mesh name (first match wins). "Tab:Path" moves the item to
another tab. Folders with fewer than MIN items fold into their parent's (or the tab's) "Other"; a folder with one subfolder is
collapsed in game. Used by harvest.py select (harvested props) and build_catalog.py (the hand-made pieces)."""
import re

MIN = 2
T = {
    'Buildings': [
        (r'kiosk|market_stand|vending_mechine', 'Stalls & Kiosks'),
        (r'awning', 'Awnings'),
        (r'tent', 'Shelters'),
        (r'scaffold', 'Scaffolding'),
        (r'water_tower', 'Water Towers'),
        (r'stand_generator', 'Industrial:Power/Generators'),
    ],
    'Furniture': [
        (r'sunbed|umbrella|deck_chair|beach', 'Outdoor'),
        (r'double_bed|single_bed|bunk|mattress|sleeping_bag', 'Bedroom/Beds'),
        (r'asian_screen', 'Screens'),
        (r'wardrobe|commode', 'Bedroom/Wardrobes & Dressers'),
        (r'poor_furniture_desk', 'Tables/Desks'),
        (r'control_panel', 'Electronics:Computers & Servers'),
        (r'office_chair|office_stool|netrunner_chair', 'Seating/Office Chairs'),
        (r'stool', 'Seating/Stools'),
        (r'sofa|couchette|bean_bag|armchair|lounge_chair', 'Seating/Sofas & Armchairs'),
        (r'bench', 'Seating/Benches'),
        (r'chair|_seat', 'Seating/Chairs'),
        (r'bar_counter|bar_a_counter|display_counter|shop_table_a_counter', 'Counters'),
        (r'desk|workstation|reception', 'Tables/Desks'),
        (r'low_table|coffee_table|side_table|afterlife', 'Tables/Coffee & Side Tables'),
        (r'bar_table|bar_a_table|nkts_bar', 'Tables/Bar Tables'),
        (r'morgue_table|lab_table|butcher|industrial_table|utility_table|shop_table|^table', 'Tables/Work Tables'),
        (r'table', 'Tables/Dining Tables'),
        (r'fridge|freezer|ice_machine', 'Kitchen/Fridges & Freezers'),
        (r'kitchen', 'Kitchen/Cabinets'),
        (r'toilet|toilette|sink|bathroom', 'Bathroom'),
        (r'shelf|shelves', 'Storage/Shelves'),
        (r'locker|file_cabinet', 'Storage/Lockers & Files'),
        (r'showcase|display_case|safe', 'Storage/Display Cases & Safes'),
        (r'cabinet|sideboard|aquarium_stand', 'Storage/Cabinets'),
        (r'cart', 'Storage/Carts'),
    ],
    'Electronics': [
        (r'laser_security_pole', 'DROP'),
        (r'traffic_light', 'Street:Street Furniture'),
        (r'airconditioner|ceiling_fan', 'Climate'),
        (r'washing_machine|vacuum_sealer|coffee_machine|microwave|kitchen_appliance|cooking_appliance|drink_machine|ice_maker|kitchen_fridge|refrigerator', 'Appliances'),
        (r'monitor|tv_|television', 'Screens'),
        (r'computing|server|router|terminal|hardware|laptop', 'Computers & Servers'),
        (r'vending|drop_point|cash_register', 'Vending & Service'),
        (r'casino|pachinko|game_machine|poker|braindance', 'Arcade & Casino'),
        (r'speaker|amplifier|dj_set|jukebox|radio|record_player', 'Audio'),
        (r'security|camera|scanner|gate', 'Security'),
        (r'medical|iv_stand|surgical', 'Medical'),
        (r'.', 'Gadgets'),
    ],
    'Lighting': [
        (r'street_lamp|light_panel|standing', 'Floor Lamps'),
        (r'ceiling|hanging|chandelier', 'Ceiling Lights'),
        (r'desk', 'Desk Lamps'),
        (r'lantern', 'Lanterns'),
        (r'candle', 'Candles'),
        (r'spotlight|studio|lab_lamp|entropy_lamp', 'Work Lights'),
        (r'.', 'Lamps'),
    ],
    'Containers': [
        (r'dumpster', 'Trash/Dumpsters'),
        (r'trash_can|trashbin', 'Trash/Trash Cans'),
        (r'garbage|cardboard_pile', 'Trash/Garbage Bags'),
        (r'foil_bag|trash_packaging|cardboard_trash|street_trash', 'Trash/Litter'),
        (r'freight|arasaka_container|industrial_container', 'Shipping Containers'),
        (r'cardboard_box|postal_box|packaging_box|foam_box', 'Boxes/Cardboard'),
        (r'delivery_crate', 'Boxes/Plastic Crates'),
        (r'cargo_box|cargo_crate|packing_crate|bullet_box|box_ammo|lootable_crate|valuable_crate|^crate', 'Boxes/Cargo Crates'),
        (r'keg', 'Barrels & Tanks/Kegs'),
        (r'barrel', 'Barrels & Tanks/Barrels'),
        (r'gas_can|gas_tank|fuel_tank|water_container|bucket|boiler|fish_tank', 'Barrels & Tanks/Tanks & Cans'),
        (r'military_case|weapon_case|ammo_case|equipment_case|gadgets_case|weapon_locker', 'Cases/Military Cases'),
        (r'toolbox', 'Cases/Toolboxes'),
        (r'suitcase|duffle|backpack|bags_|guitar_case', 'Cases/Bags & Luggage'),
        (r'chest|locker|safe|cupboard|freezer', 'Cases/Chests & Lockers'),
        (r'sack|laundry_basket|cooler', 'Sacks & Baskets'),
        (r'planter|flower_pot', 'Pots & Vases/Planters'),
        (r'vase|metalware', 'Pots & Vases/Vases'),
        (r'.', 'Other'),
    ],
    'Industrial': [
        (r'generator', 'Power/Generators'),
        (r'fuse_box|electrical_box', 'Power/Fuse Boxes'),
        (r'electrical_pole', 'Power/Power Poles'),
        (r'transformer', 'Power/Transformers'),
        (r'solar', 'Power/Generators'),
        (r'airconditioner_exterior|ventilation|rooftop_fan', 'Rooftop Units'),
        (r'pallet|forklift|trolley|lift|creeper|assembly_table', 'Pallets & Lifts'),
        (r'workshop_tool|hammer_drill', 'Tools'),
        (r'tire|wheel', 'Vehicles & Tires'),
        (r'bratsk|roller|drone', 'Vehicles & Tires'),
        (r'drug_lab', 'Machines/Lab Equipment'),
        (r'concrete_mixer|heap_pipes|metal_studs', 'Construction'),
        (r'extinguisher|hydrant|gas_pump', 'Fixtures'),
        (r'.', 'Machines/Factory'),
    ],
    'Street': [
        (r'concrete_fence', 'Fences/Concrete'),
        (r'fence', 'Fences/Metal'),
        (r'railing|queue_pole', 'Railings'),
        (r'sandbag|hesco', 'Barriers/Sandbags'),
        (r'blockade|roadblock|solid_barrier', 'Barriers/Concrete Blocks'),
        (r'road_barrier|pedestrian_barrier', 'Barriers/Road Barriers'),
        (r'tire_blocker|street_pole', 'Barriers/Bollards'),
        (r'billboard|advertising|ad_sign|price_board', 'Billboards'),
        (r'newspaper|tripod|sign', 'Street Furniture'),
    ],
    'Decor': [
        (r'weapon_rack|katana_stand|fire_axe', 'Weapons:Racks & Displays'),
        (r'trophy', 'Trophies'),
        (r'guitar|drum|keyboard|piano|microphone|cymbal|balalaika|handpan|conga', 'Music'),
        (r'gym|weights|treadmill|bike|punching', 'Sports/Gym'),
        (r'.*(basketball|billiard|surf|ring|detector)', 'Sports/Games'),
        (r'carpet', 'Rugs'),
        (r'disco_ball|dream_catcher|dashi_assets|garland|beads', 'Hanging'),
        (r'.', 'Art'),
    ],
    'Nature': [
        (r'palm', 'Palms'),
        (r'ficus|joshua|niwaki|platanus', 'Trees'),
        (r'hedge', 'Hedges'),
        (r'cactus|yucca', 'Cacti & Yucca'),
        (r'stipa|serriola|malva|bluebunch|lawn|grass|epiphyte|xanadu', 'Grass & Flowers'),
        (r'creeper|climber', 'Climbers'),
        (r'canyon', 'Rocks/Canyon Rocks'),
        (r'rock', 'Rocks/Boulders'),
        (r'.', 'Shrubs'),
    ],
    # the second harvest's gate profiles (harvest.GATES): all in Decor
    'Clutter': [
        (r'drink|soda_can|takeout_cup|sake|tea_set|glass|bar_asset|beer_tap|shaker|ice_bucket', 'Decor:Clutter/Drinks'),
        (r'food|snack|meat_bag|burrito|pizza|ramen|burger|fries|hotdog|sandwich|noodle|tofu|condiment|takeout', 'Decor:Clutter/Food'),
        (r'plate|cutlery|tableware|tray|cooking|kitchen|wok|ash_tray|bar_mat', 'Decor:Clutter/Kitchenware'),
        (r'book|magazine|newspaper|paper|menu_card|document|brush|organizer|office_tool|keyboard|vinyl', 'Decor:Clutter/Books & Desk'),
        (r'clothes|shirt|pants|jacket|skirt|silk|towel|rag|shoe|sweater|blouse|dress|_simple|camping_bag', 'Decor:Clutter/Clothes & Linen'),
        (r'medkit|medic|vial|jar|bottle|grooming|perfume|makeup|soap|cleaning|lighter', 'Decor:Clutter/Bottles & Care'),
        (r'.', 'Decor:Clutter/Odds & Ends'),
    ],
    'Posters': [(r'.', 'Decor:Posters & Flags')],
    'Signs': [(r'neon', 'Decor:Signs & Neon/Neon'), (r'.', 'Decor:Signs & Neon/Signs')],
    'Weapons': [
        (r'katana', 'Blades'),
        (r'vendor|rack|stand|shell', 'Racks & Displays'),
        (r'.', 'Guns'),
    ],
}


def path(cat, stem, fallback):
    """(tab, path) for a mesh stem in tab `cat`; 'DROP' drops it."""
    for rx, p in T.get(cat, []):
        if re.search(rx, stem):
            if p == 'DROP': return None, None
            if ':' in p: return tuple(p.split(':', 1))
            return cat, p
    return cat, fallback


def fold(items):
    """items: dicts with cat, group (a path). Folders under MIN items join their parent's Other (never the top)."""
    import collections
    for _ in range(3):
        n = collections.Counter((i['cat'], i['group']) for i in items)
        changed = False
        for i in items:
            parts = i['group'].split('/')
            if n[(i['cat'], i['group'])] < MIN and parts[-1] != 'Other':
                i['group'] = '/'.join(parts[:-1] + ['Other']); changed = True
        if not changed: break
    return items


STYLE = re.compile(r'^(poor|rich|kitsch|neokitsch|neokitsh|nkts|entropy|entropism|neomilitary|neomilitarism|neomilit|neomilirary|corpo|arasaka|militech|'
                   r'pac|bls|wwd|cmn|common|generic|simple|vs|ep1|q\d+)_')
NAME_JUNK = {'aa', 'ab', 'ac', 'ad', 'ae', 'set', 'decoset', 'standalone', 'ep1', 'v1', 'v2', 'vdr', 'bm', 'gf', 'uf', 'mf',
             'lootable', 'common', 'attachments', 'deco', 'merged', 'body', 'for', 'cheap', 'cinematic', 'neo', 'milit',
             'entropy', 'kitsch', 'neokitsch', 'neomilitary', 'neomilitarism', 'militarism', 'poor', 'rich'}   # (the style words mid-name too)
NAME_MAX = 28                                               # (a menu card's line, its letter after)


def pretty(stem):
    """A readable name from a mesh name: style words, sizes (w300, h400, l1200), numbers and variant letters go, cut at
    to NAME_MAX by its first words (the thing is the last: Combat Tower Lobby Chandelier -> Tower Lobby Chandelier);
    repeats in a folder get A, B, C later."""
    s = stem
    while True:
        t = STYLE.sub('', s)
        if t == s: break
        s = t
    words = [w.capitalize() for w in re.sub(r'workshop_tool_', '', s).replace('industrail', 'industrial').replace('largel', 'large').replace('streat', 'street').split('_')
             if len(w) > 1 and not any(ch.isdigit() for ch in w) and w not in NAME_JUNK]
    while len(words) > 1 and len(' '.join(words)) > NAME_MAX: words = words[1:]
    return ' '.join(words)[:NAME_MAX] or stem[:NAME_MAX]
