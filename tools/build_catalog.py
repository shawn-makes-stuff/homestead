"""Writes the CET mod's catalog.lua from ITEMS: bounds, colour appearances, snapping data and collision boxes per piece.

Item fields:
  key, name (short: it has to fit a menu card), group (the menu's middle level), cat, mesh
  kind: 'floor' (fills a 3 m grid cell), 'wall' (stands on a cell edge), 'post' (on a grid corner), or none (free).
        Kit pieces sit with their mesh origin on a storey level (4 m apart).
  back: for a one-sided wall (tools/sides.py), the mesh for its far side. It is turned 180 degrees about Z and set just
        behind the front, so their end caps, tops and opening reveals meet: the wall gets real depth.
  col:  collider spec: 'bbox' | ('wall', pitch) = full-thickness rectangles around openings | ('vox', pitch) | None.
"""
import collections, glob, json, math, os, re, shutil, struct, sys, warnings, gzip
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import meshes, colliders, taxonomy
import paths as hpaths                                       # (fo4_rows has a list of its own called paths)
warnings.filterwarnings('ignore')

K = 'bls_ina_building_a_'
ITEMS = [
    # the workbench: always one, can't be scrapped, opens workshop mode
    dict(key='workbench', name='Workbench', group='Workbench', cat='Furniture', mesh='industrial_table_i', col='bbox'),
    # Structure: the Badlands building kit (3 m grid, 4 m storeys)
    dict(key='floor', name='Badlands Floor', group='Floors', cat='Structure', mesh=K + 'roof_l300_w300_a', kind='floor', col='bbox'),
    dict(key='wall', name='Badlands Wall', group='Walls', cat='Structure', mesh=K + 'wall_l300_gf_a', back=K + 'wall_drywall_l300_gf_a', kind='wall', col='bbox'),
    dict(key='wall_door', name='Badlands Door', group='Doorways', cat='Structure', mesh=K + 'door_single_l300_gf_a', back=K + 'door_single_drywall_l300_gf_a', kind='wall', col=('wall', 0.1)),
    dict(key='wall_window', name='Badlands Window', group='Windows', cat='Structure', mesh=K + 'window_l300_gf_a', back=K + 'window_drywall_l300_gf_a', kind='wall', col='bbox'),
    dict(key='wall_garage', name='Badlands Garage', group='Doorways', cat='Structure', mesh=K + 'garage_l600_gf_a', back=K + 'garage_drywall_l600_gf_a', kind='wall', col=('wall', 0.1)),
    dict(key='wall_upper', name='Badlands Upper Wall', group='Walls', cat='Structure', mesh=K + 'wall_l300_a', back=K + 'wall_drywall_l300_a', kind='wall', col='bbox'),
    dict(key='parapet', name='Badlands Parapet', group='Roofs', cat='Structure', mesh=K + 'parapet_l300_a', kind='wall', col='bbox'),
    dict(key='pillar', name='Badlands Pillar', group='Supports', cat='Structure', mesh=K + 'pillar_gf_a', kind='post', col='bbox'),
    dict(key='stairs', name='Steps', group='Stairs', cat='Structure', mesh=K + 'stairs_w200_h100_a', col=('wall', 0.1)),
    # Buildings: whole prefabs
    dict(key='caravan', name='Caravan', group='Shelters', cat='Buildings', mesh='pac_wwd_trailerhouse_a_addons', col=('vox', 0.25)),
    dict(key='tent', name='Tent', group='Shelters', cat='Buildings', mesh='tent_c', col=('vox', 0.25)),
    dict(key='container', name='Skip', group='Bins & Dumpsters', cat='Containers', mesh='industrial_container_a', col=('vox', 0.2)),
    # Furniture
    dict(key='table', name='Work Table', group='Tables & Desks', cat='Furniture', mesh='industrial_table_e', col='bbox'),
    dict(key='table_small', name='Rolling Table', group='Tables & Desks', cat='Furniture', mesh='industrial_table_g', col='bbox'),
    dict(key='sofa', name='Sofa', group='Seating', cat='Furniture', mesh='poor_sofa_a_old', col=('vox', 0.15)),
    dict(key='chair', name='Chair', group='Seating', cat='Furniture', mesh='poor_residential_chair_b', col='bbox'),
    dict(key='bunk', name='Bunk Bed', group='Beds', cat='Furniture', mesh='poor_double_bed_a', col='bbox'),
    dict(key='wall_bench', name='Bench', group='Seating', cat='Furniture', mesh='wall_bench_a', col='bbox'),
    # Containers, Industrial, Lighting, Street
    dict(key='barrel', name='Barrel', group='Barrels & Tanks', cat='Containers', mesh='barrel_drum_b', col='bbox'),
    dict(key='crate', name='Cargo Crate', group='Crates & Boxes', cat='Containers', mesh='cargo_crate_b', col='bbox'),
    dict(key='delivery_crate', name='Plastic Crate', group='Crates & Boxes', cat='Containers', mesh='delivery_crate_a', col='bbox'),
    dict(key='generator', name='Generator', group='Power', cat='Industrial', mesh='stand_generator', col='bbox'),
    dict(key='solar', name='Solar Panel', group='Power', cat='Industrial', mesh='solar_panel_d', col='bbox'),
    dict(key='lamp', name='Street Lamp', group='Street Lights', cat='Lighting', mesh='street_lamp_e', col=('vox', 0.15)),
    dict(key='fence', name='Wire Fence', group='Fences & Railings', cat='Street', mesh='wire_fence_02_b_h400_l300', kind='wall', col='bbox'),
    dict(key='blockade', name='Barricade', group='Barriers', cat='Street', mesh='blockade_a', col='bbox'),
    dict(key='barrier', name='Road Barrier', group='Barriers', cat='Street', mesh='road_barrier_02_a', col='bbox'),
]
# More building kits on the same 3 m x 4 m module (measured: every one of them runs -3..0 along X,
# faces +Y, stands 0..4 m). Their walls are modelled on the outside only, so each gets a back (turned 180 degrees and set
# behind it, as the Badlands kit's drywall): solid walls and doors the plain interior kit's matching piece (the doors
# are all centred, 1.4 m: tools/openings.py), windows themselves turned round (glass: the opening stays aligned).
# Floors modelled on top only get the kit's ceiling underneath ('under').
I = 'int_common_a_'
STYLES = [
    # (style, key prefix, pieces: (group, what, mesh, back, col[, under]))
    ('Suburban', 'sub', [
        ('Walls', 'Wall', 'std_rcr_house_a_wall_a_gf_l300_a', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Upper Wall', 'std_rcr_house_a_wall_a_st_l300_a', I + 'wall_h400_l300_a', 'bbox'),
        ('Doorways', 'Door', 'std_rcr_house_a_wall_a_gf_door_single_l300_a', I + 'wall_door_single_h400_l300_a', ('wall', 0.1)),
        ('Windows', 'Window', 'std_rcr_house_a_wall_a_gf_window_l300_a', 'self', 'bbox'),
        ('Windows', 'Window B', 'std_rcr_house_a_wall_a_gf_window_l300_b', 'self', 'bbox'),
        ('Floors', 'Floor', 'std_rcr_house_a_roof_b_l300_a', None, 'bbox'),
        ('Roofs', 'Roof', 'std_rcr_house_a_roof_a_l300_a', None, 'bbox')]),
    ('Apartment', 'apt', [
        ('Walls', 'Wall', 'wbr_cha_building_a_wall_gf_w300_h400_aa', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Upper Wall', 'wbr_cha_building_a_wall_w300_h400_aa', None, 'bbox'),
        ('Doorways', 'Door', 'wbr_cha_building_c_wall_gf_gate_w300_h400_aa', I + 'wall_door_single_h400_l300_a', ('wall', 0.1)),
        ('Floors', 'Floor', 'wbr_cha_building_a_floor_w300_aa', None, 'bbox'),
        ('Roofs', 'Roof', 'wbr_cha_building_a_roof_w300_aa', None, 'bbox')]),
    ('Shopfront', 'shop', [
        ('Walls', 'Wall', 'wat_kab_building_a_wall_gf_w300_h400_aa', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Upper Wall', 'wat_kab_building_a_wall_w300_h400_aa', I + 'wall_h400_l300_a', 'bbox'),
        ('Doorways', 'Door', 'wat_kab_building_a_wall_door_gf_w300_h400_aa', I + 'wall_door_single_h400_l300_a', ('wall', 0.1)),
        ('Doorways', 'Shutter', 'wat_kab_building_a_wall_garage_shutter_w300_h400_aa', 'self', 'bbox'),
        ('Windows', 'Window', 'wat_kab_building_a_wall_window_w300_h400_aa', 'self', 'bbox'),
        ('Windows', 'Shop Window', 'wat_kab_building_a_wall_large_window_gf_w300_h400_aa', 'self', 'bbox'),
        ('Floors', 'Floor', 'wat_kab_building_f_floor_w300_aa', None, 'bbox'),
        ]),
    ('Industrial', 'ind', [
        ('Walls', 'Wall', 'std_arr_industrial_a_wall_gf_h400_l300_a', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Upper Wall', 'std_arr_industrial_a_wall_mf_h400_l300_a', I + 'wall_h400_l300_a', 'bbox'),
        ('Doorways', 'Door', 'std_arr_industrial_a_wall_gf_door_single_h400_l300_a', I + 'wall_door_single_h400_l300_a', ('wall', 0.1)),
        ('Roofs', 'Roof', 'std_arr_industrial_a_guardhouse_roof_l300_w300_a', None, 'bbox')]),
    ('Warehouse', 'wh', [
        ('Walls', 'Wall', 'int_ent_industrial_a_wall_gf_h400_l300_a', 'self', 'bbox'),
        ('Doorways', 'Door', 'int_ent_industrial_a_wall_gf_door_single_h400_l300_a', 'self', ('wall', 0.1)),
        ('Doorways', 'Double Door', 'int_ent_industrial_a_wall_gf_door_double_h400_l300_a', 'self', ('wall', 0.1)),
        ('Windows', 'Window', 'int_ent_industrial_a_wall_gf_window_h400_l300_a', 'self', ('wall', 0.1)),
        ('Floors', 'Floor', 'int_ent_industrial_a_floor_l300_a', None, 'bbox', 'int_ent_industrial_a_ceiling_l300_a'),
        ('Floors', 'Metal Floor', 'int_ent_industrial_a_floor_metal_l300_a', None, 'bbox', 'int_ent_industrial_a_ceiling_l300_a')]),
    ('Interior', 'int', [
        ('Walls', 'Wall', I + 'wall_h400_l300_a', 'self', 'bbox'),
        ('Doorways', 'Door', I + 'wall_door_single_h400_l300_a', 'self', ('wall', 0.1)),
        ('Doorways', 'Double Door', I + 'wall_door_double_h400_l300_a', 'self', ('wall', 0.1)),
        ('Windows', 'Window', I + 'wall_window_medium_h400_l300_a', 'self', ('wall', 0.1)),
        ('Windows', 'Small Window', I + 'wall_window_small_h400_l300_a', 'self', ('wall', 0.1)),
        ('Floors', 'Floor', I + 'floor_l300_a', None, 'bbox', I + 'ceiling_l300_a')]),
    ('Traditional', 'jpn', [                     # Japantown tile roofs: a slope with its ridge cap, and a hip end
        ('Roofs', 'Tile Roof', 'wbr_jpn_traditional_a_roof_top_l300_w300', None, ('vox', 0.3), I + 'ceiling_l300_a'),
        ('Roofs', 'Tile Roof Hip', 'wbr_jpn_traditional_a_roof_hipped_top_w300', None, ('vox', 0.3), I + 'ceiling_l300_a')]),
    ('Heywood', 'hey', [
        ('Walls', 'Wall', 'hey_rey_building_a_wall_l300_gf_a', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Wall B', 'hey_rey_building_a_wall_l300_gf_b', I + 'wall_h400_l300_a', 'bbox'),
        ('Walls', 'Upper Wall', 'hey_rey_building_b_wall_l300_a', I + 'wall_h400_l300_a', 'bbox')]),
]
for style, pre, pieces in STYLES:
    for pc in pieces:
        group, what, mesh, back, col = pc[:5]
        kind = 'floor' if group in ('Floors', 'Roofs') else 'wall'
        ITEMS.append(dict(key='%s_%s' % (pre, what.lower().replace(' ', '_')), name='%s %s' % (style, what), group=group + '/' + style, cat='Structure',
                          mesh=mesh, back=mesh if back == 'self' else back, under=pc[5] if len(pc) > 5 else None, kind=kind, col=col))

# Roads: the game's own street kit (street\common, road_dirt). Every piece runs -L..0 along X and -W..0 along Y
# (measured), flat, top at 0. They are 'road' pieces: 1 m snap, and a piece latches end to end onto a
# matching one already built. Lane markings and asphalt shades are their finishes.
def _roads():
    L = [('l300', '3 m'), ('l600', '6 m'), ('l900', '9 m'), ('l1200', '12 m'), ('l2400', '24 m')]
    out = []
    for w, wname, key in (('w1000', 'Large', 'road'), ('w500', 'Narrow', 'nroad')):
        for l, lname in L:
            out.append(('%s/Straight' % wname, '%s_%s' % (key, l), '%s Road %s' % (wname, lname), 'street_a_%s_%s' % (l, w)))
        out.append(('%s/Ramps & Tapers' % wname, key + '_ramp', '%s Road Ramp' % wname, 'street_a_ramp_l1200_' + w))
        for l, lname in L[1:]:
            v = '' if w == 'w1000' else '_aa'
            out.append(('%s/Damaged' % wname, '%s_dmg_%s' % (key, l), 'Damaged %s %s' % (wname, lname), 'street_a_destroyed_%s_%s%s' % (l, w, v)))
    out += [
        ('Large/Straight', 'road_l600_loop', 'Large Road 6 m B', 'street_a_l600_w1000_extra_loop'),
        ('Large/Damaged', 'road_broken', 'Cracked Large 24 m', 'street_a_l2400_w1000_broken_a'),
        ('Large/Ramps & Tapers', 'road_taper_a', 'Lane Taper', 'street_a_l900_w100_triangle_01'),
        ('Large/Ramps & Tapers', 'road_taper_b', 'Lane Taper B', 'street_a_l900_w100_triangle_02'),
        ('Large/Curves & Corners', 'road_curve90', 'Road Curve 90', 'street_a_roadtool_junction_1ln_a90_r0'),
        ('Large/Curves & Corners', 'road_curve90_walk', 'Road Curve 90 Kerbed', 'street_a_roadtool_junction_1ln_a90_r300'),
        ('Large/Curves & Corners', 'road_corner', 'Corner Fill 3 m', 'street_a_crossroad_corner_r300'),
        ('Large/Curves & Corners', 'road_corner6', 'Corner Fill 6 m', 'street_a_crossroad_corner_r600'),
        ('Large/Curves & Corners', 'road_corner7', 'Corner Fill 7 m', 'street_a_crossroad_corner_r700'),
        ('Plazas', 'road_plaza', 'Plaza 5 m', 'street_a_l500_w500_flat'),
        ('Plazas', 'plaza10', 'Asphalt 10 m', 'street_a_flat_10mx10m'),
        ('Plazas', 'plaza15', 'Asphalt 15 m', 'street_a_flat_15mx15m'),
        ('Plazas', 'plaza20', 'Asphalt 20 m', 'street_a_flat_20mx20m'),
        ('Plazas', 'plaza15d', 'Dark Asphalt 15 m', 'street_a_flat_darker_15mx15m'),
        ('Parking', 'road_parking', 'Parking Lane', 'street_a_parking_lane_l600_w300'),
        ('Parking', 'parking_end_a', 'Parking Lane End', 'street_a_parking_lane_end_a_l600_w300'),
        ('Parking', 'parking_end_b', 'Parking Lane End B', 'street_a_parking_lane_end_b_l600_w300'),
        ('Markings', 'road_crossing', 'Crossing', 'street_crossing_250x250'),
        ('Markings', 'crossing_small', 'Crossing Small', 'street_crossing_125x125'),
        ('Markings', 'stopline', 'Stop Line', 'street_a_crossroad_bar_a_w1000'),
        ('Markings', 'stopline_n', 'Stop Line Narrow', 'street_a_crossroad_bar_b_w500_a'),
        ('Markings', 'plate', 'Road Plate', 'street_a_plate_a'),
        ('Markings', 'plate_b', 'Road Plate Large', 'street_a_plate_b'),
        ('Markings', 'manhole', 'Manhole', 'street_a_deco_sewer_access_a_l120'),
        ('Markings', 'techbox', 'Utility Cover', 'street_a_deco_techbox_a_w200_l200'),
    ]
    for l, lname in L[1:]:
        out.append(('Dirt Paths', 'dirt_%s' % l, 'Dirt Path %s' % lname, 'road_dirt_a_%s_h600' % l))
    for l, lname in L[1:]:
        out.append(('Dirt Paths', 'dirt_wide_%s' % l, 'Wide Dirt Road %s' % lname, 'road_dirt_a_%s_h1100' % l))
    out += [
        ('Dirt Paths', 'dirt_end', 'Dirt Path End', 'road_dirt_a_end_l1200_h600'),
        ('Dirt Paths', 'dirt_wide_end', 'Wide Dirt Road End', 'road_dirt_a_end_l1200_h1100'),
        ('Dirt Paths', 'dirt_curve90', 'Dirt Road Curve 90', 'road_dirt_a_roadtool_junction_1ln_a90_r0'),
        ('Sidewalks/Tiles', 'walk_a', 'Sidewalk', 'street_a_sidewalk_blank_a_w300_l300'),
        ('Sidewalks/Tiles', 'walk_b', 'Sidewalk B', 'street_a_sidewalk_blank_b_w300_l300'),
        ('Sidewalks/Tiles', 'walk_c', 'Sidewalk C', 'street_a_sidewalk_blank_c_w300_l300'),
        ('Sidewalks/Tiles', 'walk_d', 'Sidewalk D', 'street_a_sidewalk_blank_d_w300_l300'),
        ('Sidewalks/Tiles', 'walk_old', 'Old Sidewalk', 'street_a_sidewalk_old_d_w300_l300'),
        ('Sidewalks/Tiles', 'walk_cracked', 'Cracked Sidewalk', 'street_a_sidewalk_old_e_w300_l300'),
        ('Sidewalks/Tiles', 'walk_strip', 'Sidewalk Strip', 'street_a_sidewalk_blank_a_w100_l300'),
        ('Sidewalks/Tiles', 'walk_broken_a', 'Broken Sidewalk', 'street_a_sidewalk_blank_a_w300_l300_destroyed_a'),
        ('Sidewalks/Tiles', 'walk_broken_b', 'Broken Sidewalk B', 'street_a_sidewalk_blank_a_w300_l300_destroyed_b'),
        ('Sidewalks/Large Tiles', 'walk6', 'Sidewalk 6 m', 'street_a_sidewalk_blank_a_w600_l600'),
        ('Sidewalks/Large Tiles', 'walk6x9', 'Sidewalk 6x9 m', 'street_a_sidewalk_blank_a_w600_l900'),
        ('Sidewalks/Large Tiles', 'walk6x12', 'Sidewalk 6x12 m', 'street_a_sidewalk_blank_a_w600_l1200'),
        ('Sidewalks/Large Tiles', 'walk6x24', 'Sidewalk 6x24 m', 'street_a_sidewalk_blank_a_w600_l2400'),
        ('Sidewalks/Large Tiles', 'walk6_old_a', 'Old Sidewalk 6 m', 'street_a_sidewalk_old_a_w600_l600'),
        ('Sidewalks/Large Tiles', 'walk6_old_b', 'Old Sidewalk 6 m B', 'street_a_sidewalk_old_b_w600_l600'),
        ('Sidewalks/Large Tiles', 'walk6_dmg', 'Damaged Sidewalk 6 m', 'street_a_sidewalk_demaged_w600_l600'),
        ('Sidewalks/Large Tiles', 'walk6x12_dmg', 'Damaged Sidewalk 12 m', 'street_a_sidewalk_demaged_w600_l1200'),
        ('Sidewalks/Corners', 'walk_corner', 'Sidewalk Corner', 'street_a_sidewalk_blank_a_corner_w300_l300'),
        ('Sidewalks/Corners', 'walk_corner6', 'Sidewalk Corner 6 m', 'street_a_sidewalk_blank_a_corner_w600_l600'),
        ('Sidewalks/Corners', 'walk_corner7', 'Sidewalk Corner 7 m', 'street_a_sidewalk_blank_a_corner_w700_l700'),
        ('Sidewalks/Corners', 'walk_inner', 'Inner Corner', 'street_a_sidewalk_blank_a_concave_corner_w300_l300'),
        ('Sidewalks/Corners', 'walk_inner6', 'Inner Corner 6 m', 'street_a_sidewalk_blank_a_concave_corner_w600_l600'),
        ('Sidewalks/Corners', 'walk_old_corner', 'Old Corner 6 m', 'street_a_sidewalk_old_corner_6x6'),
        ('Sidewalks/Ramps', 'walk_ramp', 'Curb Ramp', 'street_a_sidewalk_ramp_a_middle_w300_l300'),
        ('Sidewalks/Ramps', 'walk_ramp_l', 'Curb Ramp Left', 'street_a_sidewalk_ramp_a_left_w300_l300'),
        ('Sidewalks/Ramps', 'walk_ramp_r', 'Curb Ramp Right', 'street_a_sidewalk_ramp_a_right_w300_l300'),
        ('Sidewalks/Ramps', 'walk_ramp_corner', 'Corner Ramp', 'street_a_sidewalk_ramp_a_corner_w300_l300'),
        ('Sidewalks/Ramps', 'walk_ramp_corner6', 'Corner Ramp 6 m', 'street_a_sidewalk_ramp_a_corner_w600_l600'),
        ('Sidewalks/Features', 'walk_tree', 'Tree Planter Tile', 'street_a_sidewalk_tree_planter_a_w300_l300'),
        ('Sidewalks/Features', 'walk_techbox', 'Utility Hatch Tile', 'street_a_sidewalk_techbox_entry_a_w300_l300'),
        ('Sidewalks/Features', 'walk_techbox_b', 'Utility Hatch Tile B', 'street_a_sidewalk_techbox_entry_b_w300_l300'),
        ('Sidewalks/Features', 'walk_gutter', 'Gutter', 'street_a_gutter_a'),
        ('Curbs', 'curb', 'Curb 3 m', 'street_a_curb_blank_a_w80_l300'),
        ('Curbs', 'curb6', 'Curb 6 m', 'street_a_curb_blank_a_w80_l600'),
        ('Curbs', 'curb9', 'Curb 9 m', 'street_a_curb_blank_a_w80_l900'),
        ('Curbs', 'curb12', 'Curb 12 m', 'street_a_curb_blank_a_w80_l1200'),
        ('Curbs', 'curb24', 'Curb 24 m', 'street_a_curb_blank_a_w80_l2400'),
        ('Curbs', 'curb_thin', 'Thin Curb', 'street_a_curb_blank_w20_l300_a'),
        ('Curbs', 'curb_drain', 'Curb Drain', 'street_a_curb_storm_drain_a_w80_l300'),
        ('Curbs', 'curb_drain_b', 'Curb Drain B', 'street_a_curb_storm_drain_b_w80_l300'),
    ]
    return out


ROADS = _roads()
for group, key, name, mesh in ROADS:
    ITEMS.append(dict(key=key, name=name, group=group, cat='Roads', mesh=mesh, kind='road', col='bbox'))

# Fallout 4's workshop menu first, in its order (its pieces are imported from the player's own install); then ours
WALK_TABS = ('Structures', 'Structure', 'Roads', 'Buildings')   # (livenav.lua WALK: what a catalog without `walk` walks)
FO4_CATS = ['Structures', 'Furniture', 'Decorations', 'Power', 'Defense', 'Resources', 'Stores', 'Crafting', 'Special', 'Cages', 'Raider', 'Creation Club']
NATIVE_TAB = 'Night City'                                    # (Cyberpunk's own props, weapons and nature: one tab)
SORT = FO4_CATS + [c for c in ['Structure', 'Buildings', 'Roads', 'Furniture', 'Electronics', 'Lighting', 'Containers', 'Industrial', 'Street',
                                'Decor', 'Nature', 'Weapons', 'People'] if c not in FO4_CATS]   # (the rows' order, before the tab)
CATS = FO4_CATS + [NATIVE_TAB, 'People']                         # (the menu's tabs)
NATIVE_OUT = {'Buildings', 'Structure', 'Roads'}           # (out of the menu: Fallout's build the settlement - user,
                                                             # 2026-10-01; fences and railings are props, in)
NATIVE_MOUNTS = {'Decor', 'Electronics', 'Lighting', 'Weapons'}   # (kinds whose thin pieces may hang on a wall)


# wall props whose origin is not on their back: the back's side (looked at: the front has the vents, pickups, screen)
BACKS = {'h_poor_airconditioner_a': '+X', 'h_poor_airconditioner_b': '+X', 'h_poor_airconditioner_c': '+X',
         'h_rich_airconditioner_a': '+X', 'h_rich_airconditioner_b': '+X', 'h_poor_airconditioner_d': '-Y',
         'h_poor_airconditioner_db': '-Y', 'h_poor_fly_killer_a': '+X', 'h_tv_large_a': '+Y', 'h_speaker_a_single_a': '+Y',
         'h_surf_board_a': '-Y', 'h_bass_guitar_a': '-X', 'h_electric_guitar_a': '-X', 'h_electric_guitar_b': '-X',
         'h_electric_guitar_c': '-X', 'h_electric_guitar_d': '-X'}
CEILINGS = {'h_ceiling_lamp_long_a'}                         # (origin in its middle: hung by its top)
DUP_GUNS = re.compile(r'^h_(achilles|authority|defender|hercules|hmg|masamune|saratoga|tactician)_')   # (the real ones: make_weapons)


SEATING = re.compile(r'(?<!wheel)chair|stool|sofa|couch|bench|seat\b|bean bag|bed\b|beds\b|mattress|futon|sleeping bag', re.I)
BEDS = re.compile(r'bed\b|beds\b|mattress|futon|sleeping bag', re.I)
NOT_SEAT = re.compile(r'table(?!\s+(chair|stool))|desk|bedside|press|gym|massage|surgical|morgue(?!\s+stool)|medical|shelf|cabinet|hospital|footrest', re.I)   # (a low table's chair is a chair)


def native_seats(r):
    """seats on a Night City piece, as Fallout's furniture has them ([x, y, z, yaw, kind, top]: on the floor under the
    seat, the person's way, the kind life.lua plays, the seat's height): its kind by its name, the height the surface
    under the middle, the way the person faces from the shape - away from a chair's back, towards a bed's head (both
    as Fallout's own seats: 64 of 68 of its chairs, all its beds); a sofa a seat every 0.7 m of its length"""
    n = r['name']
    if r.get('cat') != 'Furniture' or not SEATING.search(n) or NOT_SEAT.search(n) or not r.get('meshes') or not r.get('min'): return None
    import trimesh
    g = os.path.join(HARVEST, 'glb', r['meshes'][0][0][:-5] + '.glb')
    if not os.path.exists(g): return None
    try:
        m = trimesh.load(g, force='mesh')
        v = np.r_[m.vertices, trimesh.sample.sample_surface(m, 20000, seed=0)[0]]   # (points on big flat faces too)
    except Exception: return None
    v = np.c_[v[:, 0], -v[:, 2], v[:, 1]]                    # (.glb Y-up -> the piece's space)
    lo, hi = r['min'], r['max']
    bed = BEDS.search(n) is not None
    long_x = hi[0] - lo[0] > hi[1] - lo[1]
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    def top_at(x, y, below):                                 # the highest surface under (x, y) up to `below`
        near = v[(np.abs(v[:, 0] - x) < 0.15) & (np.abs(v[:, 1] - y) < 0.15) & (v[:, 2] < below)]
        return float(near[:, 2].max()) if len(near) else None
    top = top_at(cx, cy, 0.85 if bed else 0.75)
    if top is None or top < (0.02 if bed else 0.05): return None   # (a sleeping bag lies 5 cm high, a floor cushion 10)
    high = v[v[:, 2] > top + 0.25]                           # a back, a headboard
    if bed:
        if long_x: yaw = 90.0 if (len(high) and high[:, 0].mean() < cx) else 270.0       # (towards the head)
        else: yaw = 0.0 if (not len(high) or high[:, 1].mean() > cy) else 180.0
        return [[round(cx, 3), round(cy, 3), 0.0, yaw, 'floorbed' if top < 0.3 else 'bed', round(top, 3)]]
    kind = 'stool' if re.search('stool', n, re.I) else 'couch' if re.search('sofa|couch|bench', n, re.I) else 'chair'
    if len(high):                                            # away from the back
        bx, by = high[:, 0].mean() - cx, high[:, 1].mean() - cy
        yaw = round(math.degrees(math.atan2(bx, -by)) % 360 / 90) * 90 % 360   # (facing -back, squared to the piece)
    else: yaw = 0.0
    fx, fy = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    depth = abs(fx) * (hi[0] - lo[0]) + abs(fy) * (hi[1] - lo[1])
    sx, sy = cx + fx * depth * 0.15, cy + fy * depth * 0.15   # (the seat: a little in front of the middle, off the back)
    def seat_top(x, y):                                      # the cushion: from the front back to the middle
        for f in (0, 0.15, 0.3):
            t = top_at(x - fx * depth * f, y - fy * depth * f, 0.65)
            if t and t >= 0.3: return t
        return None
    st = seat_top(sx, sy)
    if kind == 'chair' and top < 0.3 and st is None:        # (a floor cushion, a low seat: knelt on, not sat on 45 cm
        return [[round(sx, 3), round(sy, 3), 0.0, float(yaw), 'kneel', round(top, 3)]]   # over it)
    if kind != 'couch': return [[round(sx, 3), round(sy, 3), 0.0, float(yaw), kind, round(st or 0.45, 3)]]
    length = (hi[0] - lo[0]) if yaw in (0, 180) else (hi[1] - lo[1])
    k = max(1, int(length // 0.7))
    out = []
    for i in range(k):
        o = (i - (k - 1) / 2) * 0.7
        x, y = (sx + o, sy) if yaw in (0, 180) else (sx, sy + o)
        out.append([round(x, 3), round(y, 3), 0.0, float(yaw), 'couch', round(seat_top(x, y) or 0.45, 3)])
    return out


FACTIONS = [('Gangs/Valentinos', r'valentino|elgallo'), ('Gangs/Tyger Claws', r'tyger'), ('Gangs/Maelstrom', r'maelstrom'),
            ('Gangs/6th Street', r'6th'), ('Gangs/Animals', r'animal'), ('Gangs/Voodoo Boys', r'voodoo'),
            ('Gangs/Scavengers', r'scav'), ('Gangs/Wraiths', r'wraith'), ('Nomads', r'aldecaldo|nomad'),
            ('Corporations', r'arasaka|militech|miltech|kangtao|biotechnica|petrochem|cytech|kendachi|trauma|black_ops|orbital'),
            ('Police & Security', r'police|ncpd|maxtac|security|guard|sheriff'), ('Barghest', r'kurt|militia|barghest'),
            ('Cyberpsychos', r'psycho'),
            ('Shops & Bars', r'shop|vendor|barman|bartender|ripper|food|bar_|_bar|store|merchant|seller|market')]   # (first match)


def candle_tips(r):
    """a candle piece's candles (user, 2026-10-02: the funeral stand's 40 had one flame, over the stand): its thin
    standing pieces (4-6 cm across) with nothing of the mesh over their tops, one a spot; a single wide candle (a jar,
    a bottle): none - its bounds' top then (native_light)"""
    import trimesh
    g = os.path.join(HARVEST, 'glb', r['meshes'][0][0][:-5] + '.glb')
    if not os.path.exists(g): return None
    try: s = trimesh.load(g)
    except Exception: return None
    geos = list(s.geometry.values()) if hasattr(s, 'geometry') else [s]
    allv = np.vstack([np.asarray(m.vertices) for m in geos])
    allv = np.c_[allv[:, 0], -allv[:, 2], allv[:, 1]]       # (.glb Y-up -> the piece's space)
    out = []
    for m in geos:
        for piece in m.split(only_watertight=False):
            v = np.asarray(piece.vertices)
            v = np.c_[v[:, 0], -v[:, 2], v[:, 1]]
            if max(np.ptp(v[:, 0]), np.ptp(v[:, 1])) > 0.06 or np.ptp(v[:, 2]) < 0.008: continue   # (thin, standing up)
            x, y, top = v[:, 0].mean(), v[:, 1].mean(), v[:, 2].max()
            near = allv[(np.abs(allv[:, 0] - x) < 0.015) & (np.abs(allv[:, 1] - y) < 0.015)]
            if len(near) and near[:, 2].max() > top + 0.005: continue   # (under something: a leg, not a candle)
            out.append((x, y, top))
    keep, tall = [], max((t[2] for t in out), default=0)
    for t in sorted(out, key=lambda t: -t[2]):              # (a candle's parts: its highest; drips, a label under: no)
        if t[2] < tall - 0.03: break
        if all((t[0] - k[0]) ** 2 + (t[1] - k[1]) ** 2 > 0.012 ** 2 for k in keep): keep.append(t)
    return [[round(float(a), 3) for a in k] for k in keep] if len(keep) > 1 else None


CANDLE_FX = 'base\\fx\\environment\\pyro\\e_candle_fire_idle_small.effect'   # (the game's own candle flame)
FLAME_DOWN = 0.16                                            # m under a candle's tip the flame effect is spawned: its
                                                             # particles start 0.15 m over its origin (the effect's
                                                             # Initial position, read with WolvenKit), the flame's foot
                                                             # at the sprite's bottom - so the flame's foot sits 1 cm
                                                             # under the tip (user, 2026-10-02: spawned 3 cm under the
                                                             # tip the flames floated 12 cm over the candles)


def native_light(r):
    """a Night City lamp's light (the game puts a lamp's light in the world, not in its mesh): its colour, reach and how
    bright (lm: lumens, init.lua lumens() takes it as is) by its kind; where - just under its lit parts (`emit`:
    harvest.py lights, the chunks its emissive materials are on, a light for each of two lamp heads), else by its
    kind from its bounds; the emissive's colour when it says one. A candle its flame too; a glowing sign (neon) a glow
    in front of it. -> (lights, fx) or (None, None)"""
    n, lo, hi = r['name'].lower(), r['min'], r['max']
    e = r.get('emit') or {}
    sign = r['cat'] == 'Decor' and r.get('group', '').startswith('Signs & Neon')
    if r['cat'] != 'Lighting' and 'candle' not in n and not (sign and e.get('glow')): return None, None
    x, y = round((lo[0] + hi[0]) / 2, 3), round((lo[1] + hi[1]) / 2, 3)
    warm, soft, cool = [255, 170, 90], [255, 225, 190], [230, 240, 255]
    if 'candle' in n:                                       # (a flame a candle, as the game's own candle_device.ent
        tips = r.get('candles') or [[x, y, round(hi[2], 3)]]   # has them; one light for them all: a candle's dozen
        fl = [[t[0], t[1], round(t[2] - FLAME_DOWN, 3)] for t in tips]   # lumens - "stupidly bright" at a lamp's)
        mid = [round(sum(f[i] for f in fl) / len(fl), 3) for i in range(3)]
        return [dict(color=warm, radius=2.5 if len(fl) == 1 else 4.0, fade=4.0, lm=min(150, 12 * len(fl)), pos=mid)], [dict(path=CANDLE_FX, pos=f) for f in fl]
    c = e.get('color')
    c = [round(v * 255 / max(c)) for v in c] if c and max(c) > 0 else None   # (the hue; how bright is lm's)
    if sign:                                                # (off its back - the side its origin is on, the wall's -
        a = 0 if hi[0] - lo[0] < hi[1] - lo[1] else 1       # 0.3 m out in front, as far as the sign is big)
        front, out = (hi[a], 1) if abs(lo[a]) <= abs(hi[a]) else (lo[a], -1)
        size = max(h - l for h, l in zip(hi, lo))
        ls = []
        for b in e['glow'][:2]:
            p = b[:3]
            p[a] = round(front + out * 0.3, 3)
            ls.append(dict(color=c or soft, radius=round(min(8.0, max(2.5, 1.5 * size)), 2), fade=4.0, lm=200, pos=p))
        return ls, None
    if 'lantern' in n: col, rad, lm, z = warm, 4.0, 150, (lo[2] + hi[2]) / 2
    elif (r.get('mount') or {}).get('kind') == 'ceiling' or 'ceiling' in n or 'hanging' in n or 'chandel' in n: col, rad, lm, z = soft, 6.0, 600, lo[2] + 0.12
    elif 'spotlight' in n or 'studio' in n: col, rad, lm, z = cool, 8.0, 800, hi[2] - 0.15
    elif 'street lamp' in n:                                # (its head at the end of its arm, away from the pole at
        col, rad, lm, z = soft, 12.0, 800, hi[2] - 0.3      # its origin)
        a = 0 if hi[0] - lo[0] > hi[1] - lo[1] else 1
        if hi[a] - lo[a] > 1.5:
            end = hi[a] - 0.3 if abs(hi[a]) > abs(lo[a]) else lo[a] + 0.3
            x, y = (round(end, 3), y) if a == 0 else (x, round(end, 3))
    else: col, rad, lm, z = soft, 3.5 if 'desk' in n else 4.5, 250 if 'desk' in n else 400, hi[2] - 0.12
    at = [[b[0], b[1], b[2] - b[5] - 0.05] for b in e['glow'][:2]] if e.get('glow') else [[x, y, z]]
    return [dict(color=c or col, radius=rad, fade=4.0, lm=lm, pos=[round(v, 3) for v in p]) for p in at], None


def plant_profile(r):
    """a plant's shape for the outline drawn when V looks at one (init.lua plantLines: the game's outline doesn't
    draw on foliage, and its box looked like a box - user, 2026-10-02): the mesh in 7 slices bottom to top, each
    the ellipse round its vertices [z, cx, cy, rx, ry]. None without the mesh"""
    import trimesh
    g = os.path.join(HARVEST, 'glb', r['meshes'][0][0][:-5] + '.glb')
    if not os.path.exists(g): return None
    try: s = trimesh.load(g)
    except Exception: return None
    geos = list(s.geometry.values()) if hasattr(s, 'geometry') else [s]
    v = np.vstack([np.asarray(m.vertices) for m in geos])
    v = np.c_[v[:, 0], -v[:, 2], v[:, 1]]                   # (.glb Y-up -> the piece's space)
    z0, z1 = float(v[:, 2].min()), float(v[:, 2].max())
    if z1 - z0 < 0.05 or len(v) < 8: return None
    edges, out = np.linspace(z0, z1, 8), []
    for k in range(7):
        band = v[(v[:, 2] >= edges[k] - 1e-6) & (v[:, 2] <= edges[k + 1] + 1e-6)]
        if len(band) < 3: continue
        lo, hi = np.percentile(band[:, :2], 3, axis=0), np.percentile(band[:, :2], 97, axis=0)   # (a stray leaf aside)
        out.append([round(float(x), 2) for x in (edges[k] if k == 0 else edges[k + 1] if k == 6 else (edges[k] + edges[k + 1]) / 2,
                                                  (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, max(0.03, (hi[0] - lo[0]) / 2), max(0.03, (hi[1] - lo[1]) / 2))])
    return out if len(out) >= 2 else None


THICK = 0.3                                                  # m: a walking surface's collider is at least this thick


def thicken(boxes, floor):
    """thin, wide collider boxes (a floor's 3 cm slab, a stair's tread) grown downwards to THICK (not under the piece
    by more than 0.15): people walking off the game's navmesh dropped through the thin ones now and then (the walking
    log, 2026-10-02: 13-28 cm under a floor whose slab is 3 cm) - a thick box gives nothing to fall through. Boxes in
    the piece's space {cx, cy, cz, hx, hy, hz}; turned ones (10 numbers) as they are"""
    out = []
    for b in boxes:
        if len(b) == 6 and 2 * b[5] < 0.25 and b[3] >= 0.15 and b[4] >= 0.15:
            top = b[2] + b[5]
            bot = min(b[2] - b[5], max(top - THICK, floor - 0.15))
            b = [b[0], b[1], round((top + bot) / 2, 4), b[3], b[4], round((top - bot) / 2, 4)]
        out.append(b)
    return out


BURIED = re.compile(r'pole|street lamp|post|sign|fence|barrier|bollard|hydrant|blockade|tripod', re.I)   # (outdoor pieces
                                                             # with a footing meant to be in the ground: their origin on it)
def native_mount(lo, hi, key='', flat=0.02):
    """a Cyberpunk prop's mount from its bounds: all below its origin - a ceiling's; thin across X or Y with its origin
    on one face - that face is its back, against a wall (into the wall: dir, degrees in its own space); BACKS and
    CEILINGS: by key"""
    if key in CEILINGS: return dict(kind='ceiling', x=round((lo[0] + hi[0]) / 2, 3), y=round((lo[1] + hi[1]) / 2, 3), z=round(hi[2], 3), dir=0)
    if key in BACKS:
        s, a = BACKS[key][0] == '+', 'XY'.index(BACKS[key][1])
        p = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
        p[a] = hi[a] if s else lo[a]
        return dict(kind='wall', x=round(p[0], 3), y=round(p[1], 3), z=round((lo[2] + hi[2]) / 2, 3), dir=(0, 180, 90, 270)[a * 2 + (not s)])
    if hi[2] <= flat and lo[2] < -0.05:
        return dict(kind='ceiling', x=round((lo[0] + hi[0]) / 2, 3), y=round((lo[1] + hi[1]) / 2, 3), z=round(hi[2], 3), dir=0)
    for a, (into_max, into_min) in ((0, (0, 180)), (1, (90, 270))):
        if hi[a] - lo[a] < 0.15 and hi[2] - lo[2] > 0.1:
            back = hi[a] if abs(hi[a]) <= flat else lo[a] if abs(lo[a]) <= flat else None
            if back is None: continue
            p = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
            p[a] = back
            return dict(kind='wall', x=round(p[0], 3), y=round(p[1], 3), z=round((lo[2] + hi[2]) / 2, 3),
                        dir=into_max if back == hi[a] else into_min)
    return None
# People: characters placed from their records (Character.<record>), standing where they're put, not tied to any quest.
# Every one was spawned in game and checked friendly or neutral to V (Placide came up hostile and is out; River and
# Wakako have no record). The preview is a mannequin (a spawned NPC can't be moved while held); the NPC appears on E.
NPCS = [('Characters', r, n, g) for r, n, g in [
    ('Judy', 'Judy', 'f'), ('Panam', 'Panam', 'f'), ('Rogue', 'Rogue', 'f'), ('Misty', 'Misty', 'f'), ('Kerry', 'Kerry', 'm'),
    ('Victor_Vector', 'Viktor', 'm'), ('Mama_Welles', 'Mama Welles', 'f'), ('Claire', 'Claire', 'f'), ('Mitch', 'Mitch', 'm'),
    ('Saul', 'Saul', 'm'), ('Jackie', 'Jackie', 'm'), ('Takemura', 'Takemura', 'm'), ('Evelyn', 'Evelyn', 'f'),
    ('Lizzy_Wizzy', 'Lizzy Wizzy', 'f'), ('Nancy', 'Nancy', 'f'), ('Dexter', 'Dexter', 'm'), ('Carol', 'Carol', 'f'),
    ('Cassidy', 'Cassidy', 'm'), ('Santiago', 'Santiago', 'm'), ('Hanako', 'Hanako', 'f')]] + [('Locals', r, n, g) for r, n, g in [
    ('CorpoMan', 'Corpo', 'm'), ('CorpoWoman', 'Corpo Woman', 'f'), ('NightlifeMale', 'Clubber', 'm'), ('NightlifeWoman', 'Clubber Woman', 'f'),
    ('WorkoutMale', 'Jogger', 'm'), ('WorkoutFemale', 'Jogger Woman', 'f'), ('JockMale', 'Jock', 'm'), ('SlackerMale', 'Slacker', 'm'),
    ('SlackerFemale', 'Slacker Woman', 'f'), ('YoungsterMale', 'Youngster', 'm'), ('YoungsterFemale', 'Youngster Woman', 'f'),
    ('StoopKing', 'Stoop King', 'm'), ('StoopQueen', 'Stoop Queen', 'f'), ('VendorMale', 'Vendor', 'm'), ('VendorFemale', 'Vendor Woman', 'f'),
    ('WorkerMale', 'Worker', 'm'), ('Waitress', 'Waitress', 'f'), ('CookMale', 'Cook', 'm'), ('NurseFemale', 'Nurse', 'f'),
    ('MedicalMale', 'Medic', 'm'), ('Monk', 'Monk', 'm'), ('HomelessMan', 'Drifter', 'm'), ('HomelessFemale', 'Drifter Woman', 'f'),
    ('AldecaldosMale', 'Nomad', 'm'), ('AldecaldosFemale', 'Nomad Woman', 'f'), ('CitizenBikerMale', 'Biker', 'm'),
    ('CitizenBikerFemale', 'Biker Woman', 'f'), ('CitizenRichMale', 'Suit', 'm'), ('CitizenRichFemale', 'Socialite', 'f'),
    ('MediaWoman', 'Reporter', 'f'), ('Mallrat', 'Mallrat', 'm'), ('TenantMale', 'Local', 'm'), ('TenantWoman', 'Local Woman', 'f'),
    ('CreoleMan', 'Islander', 'm'), ('CreoleWoman', 'Islander Woman', 'f'), ('FreakMale', 'Freak', 'm'), ('FreakFemale', 'Freak Woman', 'f'),
    ('AsianVendorMale', 'Street Vendor', 'm'), ('AsianVendorFemale', 'Street Vendor Woman', 'f'), ('LowlifeMale', 'Lowlife', 'm'),
    ('LowlifeWoman', 'Lowlife Woman', 'f'), ('JunkieMale', 'Junkie', 'm')]]
MANNEQUIN = {'m': 'base\\environment\\decoration\\small_shops\\stands\\mannequin_real_bake\\mannequin_real_man_a_bake.mesh',
             'f': 'base\\environment\\decoration\\small_shops\\stands\\mannequin_real_bake\\mannequin_real_woman_a_bake.mesh'}
HARVEST = os.path.join(hpaths.work(), 'harvest')
OUT = os.path.join(hpaths.out_cet(), 'catalog.lua')


_ESC = str.maketrans({'\\': '\\\\', '"': '\\"', **{chr(i): '\\%03d' % i for i in range(32)}})   # (Lua's \ddd: three
                                                             # digits, so a digit after one can't join it)


def lua(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return repr(round(float(v), 3))
    if isinstance(v, str): return '"' + v.translate(_ESC) + '"'
    if isinstance(v, (list, tuple)): return '{' + ', '.join(lua(x) for x in v) + '}'
    if isinstance(v, dict): return '{ ' + ', '.join('%s = %s' % (k, lua(x)) for k, x in v.items() if x is not None) + ' }'
    raise TypeError(v)


def geometry(name):
    """(main +Y face plane, lowest Y of the end caps) of a wall mesh, in its own space."""
    m = colliders.load(name)
    n, a, c = m.face_normals, m.area_faces, m.triangles_center
    up = n[:, 1] > 0.9
    planes = {}
    for y, w in zip(np.round(c[up, 1], 2), a[up]): planes[y] = planes.get(y, 0) + w
    face = max(planes.items(), key=lambda t: t[1])[0]
    ends = np.abs(n[:, 0]) > 0.9
    capmin = float(m.vertices[m.faces[ends]].reshape(-1, 3)[:, 1].min())
    return float(face), capmin


NAV_MIN = 200                                                # (boxes: more, and LiveNav takes the piece from a file)


def navfiles(rows):
    """LiveNav's box files (modules/livenav.lua): a piece with over NAV_MIN static boxes (cboxes, else boxes: what it
    sends) as <work>/nav/<key>.f32 - little-endian float32, 10 a box (cx, cy, cz, hx, hy, hz, qi, qj, qk, qr; no turn:
    0, 0, 0, 1), the numbers catalog_<n>.lua holds (LiveNav's tools/hsboxes.py, byte for byte: tools/dev/check_navfiles.py)
    - and the file's path in its row (navfile). LiveNav.AddBoxesFile reads it whole; through CET as a table the Large
    Shack's 53,530 floats were reckoned at 15-55 ms a call (LiveNav NOTES.md 15)"""
    d = os.path.join(hpaths.work(), 'nav')
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for r in rows:
        bs = r['cboxes'] if r.get('cboxes') is not None else r.get('boxes')
        if not bs or len(bs) <= NAV_MIN: continue
        f = [round(float(v), 3) for b in bs for v in list(b[:6]) + (list(b[6:10]) if len(b) >= 10 else [0, 0, 0, 1])]
        r['navfile'] = os.path.join(d, r['key'] + '.f32')
        with open(r['navfile'], 'wb') as o: o.write(struct.pack('<%df' % len(f), *f))


NATIVE_JSON = os.path.join(hpaths.ROOT, 'data', 'catalog_native.json.gz') if hpaths.FROZEN else os.path.join(hpaths.work(), 'catalog_native.json.gz')


def main():
    # Cyberpunk's own pieces are made here, from the game's files we extracted (source/meshes, the harvest); a player's
    # PC hasn't those: their rows ship, made here (source/catalog_native.json.gz), and the import adds Fallout's
    if os.path.isdir(meshes.OUT):
        rows = native()
        with open(NATIVE_JSON, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as z:   # (no time inside:
            z.write(json.dumps(rows).encode('utf-8'))                                               # same rows, same file)
    else:
        with gzip.open(NATIVE_JSON, 'rt', encoding='utf-8') as f: rows = json.load(f)
    # the in-game settings' Fallout 4 pieces / Night City pieces, off: theirs aren't in the catalog (people stay)
    off = {} if not hpaths.FROZEN else hpaths.kv(os.path.join(hpaths.game_cet(), 'settings.txt'))
    nc, fo4 = off.get('importNC') != '0', off.get('importFo4') != '0'
    if not nc: rows = [r for r in rows if r.get('npc') or r.get('cat') == 'People' or r.get('key') in ('workbench', 'boundary')]
    fo4_rows(rows + (weapon_rows() if nc else []), fo4)


def weapon_rows():
    """every weapon in the player's game (tools/make_weapons.py, at import: an expansion they haven't, its weapons
    aren't there): the game's own weapon, one each, as a prop - upright against a wall (its +X side to it), on its
    side on a floor or a table (`lie`)"""
    rows = []
    wp = os.path.join(hpaths.work(), 'weapons.json')
    for w in json.load(open(wp)) if os.path.exists(wp) else []:
        lo, hi = w['min'], w['max']
        rows.append(dict(key='wpn_' + w['preset'].lower(), name=w['name'], group=w['kind'], cat='Weapons', template='homestead\\weapons.ent',
                         apps=[w['preset'] + '__' + n for n in w['looks']], lie=True, meshes=[],
                         cmeshes=[[p[0], p[2], p[3], p[4], 0, p[1]] for p in w.get('parts', [])],   # (its menu card: modules/cards.lua)
                         min=lo, max=hi, base=[0.0, 0.0, lo[2]],
                         mount=dict(kind='wall', x=hi[0], y=round((lo[1] + hi[1]) / 2, 3), z=round((lo[2] + hi[2]) / 2, 3), dir=0)))
    return rows


def native():
    names = [m for it in ITEMS for m in [it['mesh'], it.get('back'), it.get('under')] if m]
    meshes.fetch(names)
    rows = []
    for it in ITEMS:
        mn, mx, apps, depot = meshes.info(it['mesh'])
        mn, mx = list(mn), list(mx)
        parts = [[depot, 0, 0, 0, 0]]                       # {path, x, y, z, yaw[, app]} in the item's mesh space
        face = None
        if it.get('kind') == 'wall':
            face = (mn[1] + mx[1]) / 2                       # two-sided: centred on the edge
        if it.get('back'):
            bmn, bmx, _, bdepot = meshes.info(it['back'])
            face, fcap = geometry(it['mesh'])
            _, bcap = geometry(it['back'])
            # turned 180 degrees about Z (y -> ty - y): its end caps end where the front's begin
            ty = fcap + bcap
            parts.append([bdepot, round(mn[0] + mx[0], 3), round(ty, 3), 0, 180] + ([] if it['back'] == it['mesh'] else ['default']))
            mn[1] = min(mn[1], ty - bmx[1])
            mx[1] = max(mx[1], ty - bmn[1])
        if it.get('under'):                                  # a ceiling under a floor modelled on top only
            umn, umx, _, udepot = meshes.info(it['under'])
            uz = mn[2] - umx[2]
            parts.append([udepot, round((mn[0] + mx[0]) / 2 - (umn[0] + umx[0]) / 2, 3), round((mn[1] + mx[1]) / 2 - (umn[1] + umx[1]) / 2, 3), round(uz, 3), 0, 'default'])
            mn[2] = min(mn[2], uz + umn[2])
        col = it.get('col')
        if col == 'bbox':
            boxes = [[(mx[i] + mn[i]) / 2 for i in range(3)] + [(mx[i] - mn[i]) / 2 for i in range(3)]]
        elif col and col[0] == 'wall':
            boxes = [list(b) for b in colliders.boxes(it['mesh'], col[1], extrude=1, minvol=0.01)]
            for b in boxes:                                  # full depth, back included
                b[1], b[4] = (mn[1] + mx[1]) / 2, (mx[1] - mn[1]) / 2
        elif col and col[0] == 'vox':
            boxes = [list(b) for b in colliders.boxes(it['mesh'], col[1], minvol=0.02)]
        else:
            boxes = []
        rows.append(dict(key=it['key'], name=it['name'], group=it['group'], cat=it['cat'], kind=it.get('kind'), face=face, meshes=parts,
                         apps=apps or ['default'], min=mn, max=mx, base=[(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, 0.0] if it.get('kind') else colliders.ground(colliders.load(it['mesh']).vertices, mn, mx), boxes=[[round(v, 3) for v in b] for b in boxes]))
        print('%-16s %-6s %3d boxes  face %s  depth %.2f..%.2f  %s' % (it['key'], it.get('kind') or '-', len(boxes),
              'none' if face is None else '%.2f' % face, mn[1], mx[1], depot.split('\\')[-1]))
    # the harvest (tools/harvest.py): every other game prop that passed its gates, sorted into the same tabs; a lamp's
    # or a sign's lit parts (harvest.py lights) as `emit`, shown in its lit look first
    have = {r['meshes'][0][0].lower() for r in rows if r.get('meshes')}
    lp = os.path.join(HARVEST, 'lights.json')
    lit = json.load(open(lp)) if os.path.exists(lp) else {}
    shapes = json.load(open(os.path.join(HARVEST, 'shape.json')))
    for h in json.load(open(os.path.join(HARVEST, 'items.json'))):
        if h['mesh'].lower() in have or 'boxes' not in shapes.get(h['key'], {}): continue
        sh = shapes[h['key']]
        rows.append(dict(key=h['key'], name=taxonomy.pretty(os.path.basename(h['mesh'].replace('\\', '/'))[:-5]), group=h['group'], cat=h['cat'], meshes=[[h['mesh'], 0, 0, 0, 0]], apps=h['apps'],
                         min=[round(v, 3) for v in h['min']], max=[round(v, 3) for v in h['max']], base=sh['base'], boxes=sh['boxes']))
    for r in rows:
        e = lit.get((r.get('meshes') or [['']])[0][0].lower())
        if e and e.get('glow'):
            r['emit'] = e
            if e['lit'] != r['apps'][0]: r['apps'] = [e['lit']] + [a for a in r['apps'] if a != e['lit']]
            if e.get('off') and e['off'] != e['lit']: r['off'] = e['off']   # (its look with every lit part dark: init.lua
                                                                             # shows it while the lamp is off)
    geo = json.load(open(os.path.join(HARVEST, 'geom.json')))
    def person(key, name, group, record, g):
        gm = geo[MANNEQUIN[g]]
        rows.append(dict(key=key, name=name, group=group, cat='People', npc=True, record=record,
                         meshes=[[MANNEQUIN[g], 0, 0, 0, 0]], apps=['default'], min=[-0.3, -0.3, 0.0], max=[0.3, 0.3, round(gm['max'][2], 3)],
                         base=[0.0, 0.0, 0.0], boxes=[]))
    known = {}
    for group, record, name, g in NPCS:
        known['Character.' + record] = g
        if group == 'Locals': person('npc_' + record.lower(), name, group, 'Character.' + record, g)
    # every named character (tools/people.py from the game's own records; hostile ones too since 2026-10-05: the mod makes
    # whoever is placed keep the peace):
    # the main ones (a plain Character.<Name> record) together, the rest by who they are (their attitude group and
    # record: the gang, corp, police...; shops and bars), everyone else A-Z. A character whose record the player's
    # game lacks (an expansion not installed) is hidden at load (init.lua).
    pp = os.path.join(hpaths.work(), 'survey', 'people.json')
    for p in (json.load(open(pp, encoding='utf-8')) if os.path.exists(pp) else []):
        tail = p['record'].split('.', 1)[1]
        main = p.get('main') or not re.match(r'(mq|sq|q|ma|ep1|dlc|sts|mws|cbj|sa|minor|story|side|job|hey|bd|cz)\d*_', tail, re.I) and tail.count('_') <= 1
        first = p['name'][:1].upper()
        rng = next((r for r in ('ABC', 'DEF', 'GHI', 'JKL', 'MNO', 'PQR', 'STU', 'VWXYZ') if first in r), '#')
        who = (p['attitude'] + ' ' + p['record']).lower()
        group = p.get('group') or 'Main Characters' if p.get('group') or main else next((g for g, rx in FACTIONS if re.search(rx, who)), None) or             'Civilians/' + (rng[0] + '-' + rng[-1] if rng != '#' else '#')
        person('npc_' + re.sub(r'\W+', '_', p['record'].split('.', 1)[1].lower()), p['name'], group, p['record'], known.get(p['record'], 'm'))
        if p.get('old'): rows[-1]['hidden'] = True              # (no longer offered; one placed still loads)
    # menu folders: Structure is the piece's type first, then its style (Walls > Heywood: every wall in one place);
    # everything else by tools/taxonomy.py; locals by who they are; then tiny folders fold into Other
    for r in rows:
        if r['cat'] == 'Structure' and '/' not in r['group']:
            r['group'] = r['group'] + '/Badlands'
        elif r['cat'] in taxonomy.T and not r['key'].startswith('h_') and r.get('meshes'):
            stem = r['meshes'][0][0].split('\\')[-1][:-5]
            r['cat'], r['group'] = taxonomy.path(r['cat'], stem, r['group'])
    for group, record, name, g in NPCS:
        if group == 'Locals':
            next(r for r in rows if r['key'] == 'npc_' + record.lower())['group'] = 'Locals/' + ('Men' if g == 'm' else 'Women')
    taxonomy.fold([r for r in rows if r['cat'] not in ('Structure', 'Roads', 'People')])
    styles = collections.defaultdict(set)                      # a type in one style only: no style folder (Stairs > Steps)
    for r in rows:
        if r['cat'] == 'Structure': styles[r['group'].split('/')[0]].add(r['group'])
    for r in rows:
        if r['cat'] == 'Structure' and len(styles[r['group'].split('/')[0]]) == 1: r['group'] = r['group'].split('/')[0]
    for r in rows:                                          # candles: where each one's flame is (native_light)
        if r.get('cat') == 'Lighting' and 'candle' in r['name'].lower() and r.get('meshes'):
            t = candle_tips(r)
            if t: r['candles'] = t
    for r in rows:                                          # lamps' lights and signs' glow (here, with their lit
        if r.get('min') and r.get('meshes'):                # parts: a player's PC hasn't the meshes)
            ls, fx = native_light(r)
            if ls: r['lights'] = ls
            if fx: r['fx'] = fx
        r.pop('emit', None)
    for r in rows:                                          # plants: their shape, for the outline when looked at
        if r.get('cat') == 'Nature' and r.get('meshes'):    # (here, with the meshes: a player's PC hasn't them)
            pr = plant_profile(r)
            if pr: r['profile'] = pr
    n = 0
    for r in rows:                                          # Night City's furniture: where people sit and sleep
        s = native_seats(r)
        if s: r['seats'], n = s, n + 1
    print(n, 'Night City pieces with seats')
    return rows


THUMBS_JSON = os.path.join(hpaths.ROOT, 'data', 'thumbs.json') if hpaths.FROZEN else os.path.join(hpaths.work(), 'thumbs.json')
TURN_THUMB = {'h_sale_signage', 'h_unique_signage_the_hell', 'h_quest_signage_b_mistys', 'h_neon_dirty_deck',   # (3D letter
              'h_signage_biotechnica_a', 'h_unique_signage_afterlife', 'h_unique_signage_atlantis',              # signs seen
              'h_unique_signage_derevaja_dojo', 'h_unique_signage_dicky_twister', 'h_unique_signage_totentanz',  # from behind,
              'h_weapon_dealer_b', 'h_unique_signage_el_pinche_pollo_1'}                                         # mirrored)


def thumbs(rows, fo4_all):
    """the menu's thumbnails (tools/make_thumbs.py, dev time: Blender; shipped with the mod): an item's `thumb` is
    "<atlas>|<key>" when its atlas has it (source/thumbs.json). Run here with the meshes, the items to render go to
    source/thumb_items.json: [key, parts ([glb, x, y, z, yaw(, quat, scale, chunk mask)]), {glb: {material: [colour
    texture (tinted: __tint__rr_gg_bb; None: glass), alpha threshold or None(, opacity)]}}, view (thumbs_blender.py)] -
    Fallout's with their textures, Cyberpunk's own by tools/nc_textures.py; a person by their look's meshes
    (tools/npc_looks.py), a weapon by its parts: both exported by nc_textures.py"""
    atlases = json.load(open(THUMBS_JSON)) if os.path.exists(THUMBS_JSON) else {}
    where = {k: a for a, parts in atlases.items() for k in parts}
    for r in rows:
        if r['key'] in where: r['thumb'] = where[r['key']] + '|' + r['key']
    if hpaths.FROZEN or not os.path.isdir(meshes.OUT): return
    from nc_textures import look_glb
    byk = {p['key']: p for p in fo4_all}
    lp = os.path.join(hpaths.work(), 'survey', 'people_looks.json')
    looks = json.load(open(lp)) if os.path.exists(lp) else {}
    tint = lambda m: m['color'] + ('__tint__' + '_'.join('%02x' % round(min(max(c, 0), 1) * 255) for c in m['tint'])
                                   if m.get('tint') and m['tint'] != [1.0, 1.0, 1.0] else '')
    items = []
    for r in rows:
        if r.get('hidden') or r.get('stashed'): continue
        if r.get('npc'):
            parts = [[look_glb(m, look), 0, 0, 0, 0, None, None, mask] for m, look, mask in looks.get(r['record'], [])]
            parts = [q for q in parts if os.path.exists(q[0])]
            if parts: items.append([r['key'], parts, {}, 'person'])
        elif r.get('cmeshes'):                              # (a weapon: its parts where its .app puts them)
            parts = [[look_glb(m[0], m[5]), m[1], m[2], m[3], 0] for m in r['cmeshes']]
            parts = [q for q in parts if os.path.exists(q[0])]
            if parts: items.append([r['key'], parts, {}, 'side'])
        elif r.get('fo4'):
            p = byk.get(r['key'])
            if not p: continue
            parts = [[p['glb'], 0, 0, 0, 0]] * bool(p.get('glb')) + [[pt['glb'], pt['at'][0], pt['at'][1], pt['at'][2], 0, [pt['at'][4], pt['at'][5], pt['at'][6], pt['at'][3]]]
                                               for pt in p.get('parts', []) if pt.get('glb')]
            if r['key'].startswith('fo4_pa_'): parts = [[q[0], 0, 0, 0, 180] for q in parts]   # (power armour faces +Y: its front to the camera)
            if (p.get('glow') or {}).get('glb'): parts.append([p['glow']['glb'], 0, 0, 0, 0])
            mats = {}
            for o in [p] + p.get('parts', []) + ([p['glow']] if p.get('glow') else []):
                if o.get('glb'):
                    mats[o['glb']] = {m['name']: [tint(m), (m['alpha_ref'] / 255 if m.get('alpha_test') else None)] if m.get('color') else [None, None, 0.5]
                                      for m in o.get('materials', []) if m.get('color') or m.get('glass')}
            if parts: items.append([r['key'], parts, mats, None])
        elif r.get('meshes'):
            parts = []
            for m in r['meshes']:
                g = os.path.join(HARVEST, 'glb', m[0][:-5] + '.glb')
                if not os.path.exists(g): continue
                q = [m[6], m[7], m[8], m[9]] if len(m) > 9 else None
                s = [m[10], m[11], m[12]] if len(m) > 12 else None
                parts.append([g, m[1], m[2], m[3], m[4], q, s])
            if parts: items.append([r['key'], parts, {}, 'flip' if r['key'] in TURN_THUMB else None])
    json.dump(items, open(os.path.join(hpaths.work(), 'thumb_items.json'), 'w'), indent=0)
    print(len(items), 'items to render thumbnails for (tools/make_thumbs.py)')


def fo4_rows(rows, fo4=True):
    # Fallout 4's own pieces, converted from the player's install (tools/fo4/convert.py + build.py; FO4_IMPORT.md): their
    # menu is Fallout's (Structures > Wood > Floors: tab Structures, folder Wood/Floors); they snap to each other through
    # their connect points (init.lua fo4Placement).
    def fo4_point(c):                                        # a connect point: where, and the way it faces (yaw, degrees):
        w, x, y, z = c['rot']                                # its +Y turned, on the ground (Fallout stores the quaternion
        fx, fy = 2 * (x * y - w * z), 1 - 2 * (x * x + z * z)   # w first; a doorway's is often tilted as well - a yaw
        yaw = (math.degrees(math.atan2(-fx, fy)) if math.hypot(fx, fy) >= 0.3    # read as if it turned about Z alone was
               else math.degrees(math.atan2(2 * (x * y + w * z), 1 - 2 * (y * y + z * z))))   # 90 off: doors stood open)
        return dict(name=c['name'], x=c['pos'][0], y=c['pos'][1], z=c['pos'][2], yaw=round(yaw % 360, 2))
    def fo4_mount(p):                                        # Fallout's P-WS-Autoplace: sticks to a surface there, its +Y
        for c in p['connect']:                               # into the surface (wall decor: a wall; hanging ones: a ceiling)
            if c['name'].lower() == 'p-ws-autoplace':
                w, x, y, z = c['rot']
                Y = (2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x))
                kind = 'wall' if abs(Y[2]) < 0.3 else 'ceiling' if Y[2] > 0.7 else None
                if kind == 'wall' and faces_in(p, c, Y): Y = (-Y[0], -Y[1], Y[2])    # (Nuka-World's signs: the point turned
                if kind: return dict(kind=kind, x=c['pos'][0], y=c['pos'][1], z=c['pos'][2], dir=round(math.degrees(math.atan2(Y[1], Y[0])) % 360, 2))
    def faces_in(p, c, Y):                                   # round: their face would be to the wall, or in it)
        """a wall piece whose printed face points into the wall (its area-weighted normal along +Y), or whose body is
        wholly on the wall's side of its point"""
        import trimesh
        m = trimesh.load(p['glb'], force='mesh')
        f = (m.face_normals * m.area_faces[:, None]).sum(0) / max(float(m.area_faces.sum()), 1e-9)
        if f[0] * Y[0] - f[2] * Y[1] > 0.05: return True     # (the .glb is Y-up: piece Y = -glb Z)
        d = [(a - c['pos'][0]) * Y[0] + (b - c['pos'][1]) * Y[1] for a in (p['min'][0], p['max'][0]) for b in (p['min'][1], p['max'][1])]
        return max(d) > 0.03 and -min(d) < 0.005
    # Fallout's add-on effects as Cyberpunk ones (tools/fo4/lights.py `effects`): fire and smoke for now (sparks, mist
    # and the like come with power, which we don't have); points of one effect closer than 0.4 m are one
    FX = {'fire': 'base\\fx\\environment\\pyro\\e_fire_idle_small.effect',
          'barrel': 'base\\fx\\environment\\pyro\\e_fire_idle_small_barrel.effect',     # (the game's own barrel fire)
          'smoke': 'base\\fx\\environment\\smoke\\e_smoke_ambient_interior_slow_rise_0p5x2_strong.effect'}
    def fo4_fx(p):
        out = []
        for e in p.get('effects', []) + [dict(model='fire', pos=f) for f in p.get('fires', [])]:
            n = os.path.basename(e['model'])
            k = 'fire' if 'fire' in n and 'spray' not in n else 'smoke' if 'smoke' in n else None
            if k == 'fire' and 'barrel' in p['key']: k = 'barrel'
            if k and not any(f['path'] == FX[k] and math.dist(f['pos'], e['pos']) < 0.4 for f in out): out.append(dict(path=FX[k], pos=e['pos']))
        return out
    # an animated piece (tools/fo4/anim.py): its moving parts are meshes of their own after the static one, each where
    # it rests (x, y, z, quaternion i, j, k, r); `anim` its sequences - per frame per part x, y, z, i, j, k, r, flat.
    # Its boxes: static and parts' (placement, aiming); `cboxes` the static ones and `pcol` each part's (colliders,
    # a part's off while it's away from its rest: an open door lets you through)
    def fo4_meshes(p):
        ms = [[p['mesh'], 0, 0, 0, 0]] if p.get('mesh') else []
        for part in p.get('parts', []):
            x, y, z, w, qx, qy, qz = part['at']
            ms.append([part['mesh'], x, y, z, 0, '', qx, qy, qz, w])
        if p.get('glow'): ms.append([p['glow']['mesh'], 0, 0, 0, 0])   # (last: the lit glow, init.lua lamp switches it)
        return ms
    def fo4_anim(p):
        a = p.get('anim')
        if not a or not p.get('parts'): return {}
        seqs = {}
        for name, s in a['seqs'].items():
            flat = []
            for fr in s['frames']:
                for x, y, z, w, qx, qy, qz in fr: flat += [x, y, z, qx, qy, qz, w]
            seqs[name] = dict(loop=s['loop'], dur=s['dur'], f=flat)
        return dict(anim=dict(rest=a['rest'], first=2 if p.get('mesh') else 1, n=len(p['parts']), seqs=seqs),
                    cboxes=p['boxes'], pcol=[part['boxes'] for part in p['parts']])
    # Fallout's menu, tidied (user, 2026-10-01: a Prefabs folder holds whole buildings, not their roofs and corners):
    # a piece in the wrong folder of its kit moves to the sibling folder it is (only when that folder exists); a
    # record with no name gets a readable one
    MOVES = [('Prefabs', lambda n: n == 'Roof', 'Roofs'), ('Prefabs', lambda n: n.startswith('Wall - '), 'Walls'),
             ('Miscellaneous', lambda n: n == 'Door', 'Doors'), ('Miscellaneous', lambda n: n.startswith('Roof '), 'Roofs'),
             ('Chairs', lambda n: n == 'Table', 'Tables'), ('Miscellaneous', lambda n: n == 'Ottoman', 'Chairs')]
    NAMES = [(r'^RaiderCampPole(\d+)(SM|MED|LG)?$', lambda m: 'Raider Camp Pole' + {'SM': ' - Small', 'MED': ' - Medium', 'LG': ' - Large'}.get(m.group(2), '')),
             (r'^WorkshopPortraitCabot(\d+)$', lambda m: 'Cabot Portrait')]
    # a Fallout container stores things as Cyberpunk does: the game's own stash device rides in it (hidden, its
    # collider made the container's shape: init.lua onEntity), so F at it opens V's stash - one storage shared by
    # every container and V's apartments, as Fallout's workshops share theirs
    STASH = 'base\\gameplay\\devices\\stash\\stash.ent'
    fo4_all = json.load(open(fp)) if fo4 and os.path.exists(fp := os.path.join(hpaths.work(), 'fo4', 'pieces.json')) else []
    folders = {tuple(p['menu']) for p in fo4_all}
    def fo4_menu(p):
        m = list(p['menu'])
        for where, test, to in MOVES:
            if m[-1] == where and test(p['name']) and tuple(m[:-1] + [to]) in folders: return m[:-1] + [to]
        return m
    def fo4_name(n):
        for pat, f in NAMES:
            if (x := re.match(pat, n)): return f(x)
        return n
    for p in fo4_all:
        p['menu'], p['name'] = fo4_menu(p), fo4_name(p['name'])
    for p in fo4_all:
        if 'VR Workshops' in p['menu']: continue             # (base-game Creation Club content: VR spawners, only for Fallout's VR sim)
        if not p.get('mesh') and not p.get('parts'): continue
        if p['menu'][0] == 'Structures': p['boxes'] = thicken(p['boxes'], p['min'][2])   # (floors, stairs, roofs: walked on)
        rows.append(dict(key=p['key'], name=p['name'], group='/'.join(p['menu'][1:]) or p['menu'][0], cat=p['menu'][0] if p['menu'][0] in FO4_CATS else 'Special', fo4=True,
                         meshes=fo4_meshes(p), apps=['default'], min=p['min'], max=p['max'], base=p['base'],
                         **({'glow': len(fo4_meshes(p))} if p.get('glow') else {}),
                         boxes=p['boxes'] + [b for part in p.get('parts', []) for b in part['boxes']], **fo4_anim(p),
                         order=p.get('order', 0), **({'lights': p['lights']} if p.get('lights') else {}),
                         **({'fx': fx} if (fx := fo4_fx(p)) else {}),
                         **({'snd': p['sounds']} if p.get('sounds') else {}),
                         **({'seats': p['seats']} if p.get('seats') else {}),
                         **({'walk': True} if p.get('nvnm') or p.get('ramps') else {}),   # (Fallout walks it, or a stair ramp)
                         **{k: p[k] for k in ('snapR', 'ovl', 'must', 'ignoreOcc', 'vbox') if k in p},   # (snapping: convert.snap_props)
                         **({'sink': round(c['pos'][2] - p['base'][2], 3)} if (c := next((c for c in p['connect'] if c['name'].lower() == 'p-ws-sinkmax'), None)) else {}),   # (how far into the ground it may go: held, lifted out of it by up to that)
                         **({'stash': True, 'ents': [dict(path=STASH, app='default', x=0.0, y=0.0, z=0.0, q=[0.0, 0.0, 0.0, 1.0])]}
                            if p.get('kind') == 'CONT' else {}),
                         **({'connect': pts} if (pts := [fo4_point(c) for c in p['connect'] if not c['name'].upper().startswith('P-WS')]) else {}),
                         **({'mount': m} if (m := fo4_mount(p)) else {}),
                         **({'pivot': [c['pos'][0], c['pos'][1]]} if (c := next((c for c in p['connect'] if c['name'].lower() == 'p-ws-rotation'), None)) else {})))   # (what it turns about, held)
    # we spawn nothing from Fallout's cages: one plain cage per size ("Small Cage", ...) and one arena contestant
    # platform, the creature ones hidden (user, 2026-09-30; hidden, so placed ones still load)
    seen = set()
    for r in sorted((r for r in rows if r.get('fo4')), key=lambda r: r['order']):
        g = r['group']
        if r['cat'] == 'Cages' and g.endswith(' Cages'): kind, name = g, g[:-1]
        elif r['cat'] == 'Cages' and g == 'Arena': kind, name = g, 'Arena Contestant Platform'
        else: continue
        if kind in seen: r['hidden'] = True
        else: seen.add(kind); r['name'] = name
    # upper walls: each ground wall knows its twin without the foundation lip, and the twin leaves the menu
    TWINS = {'wall': 'wall_upper', 'sub_wall': 'sub_upper_wall', 'apt_wall': 'apt_upper_wall', 'shop_wall': 'shop_upper_wall',
             'ind_wall': 'ind_upper_wall', 'hey_wall': 'hey_upper_wall'}
    byk = {r['key']: r for r in rows}
    for g, u in TWINS.items():
        if g in byk and u in byk: byk[g]['upper'] = u; byk[u]['hidden'] = True   # (Night City's pieces off: none of them)
    TYPES = ['Walls', 'Doorways', 'Windows', 'Floors', 'Roofs', 'Supports', 'Stairs']
    rows.sort(key=lambda r: (SORT.index(r['cat']), (TYPES.index(r['group'].split('/')[0]) if r['group'].split('/')[0] in TYPES else 99) if r['cat'] == 'Structure'
                             else '%06d' % r['order'] if r.get('fo4') else '' if r['cat'] == 'Roads'
                             else (r['group'], r['max'][2] - r['min'][2]) if r['cat'] == 'Nature' and r.get('min')   # (plants small to tall)
                             else r['group'].replace('Other', '~')))   # Other last; Fallout's in its menu's order
    print(len(rows), 'items')
    for r in rows:                                          # (read here only, never in game: order sorted the rows,
        r.pop('order', None); r.pop('candles', None)        # candles placed native_light's flames)
    # what only a piece in hand or in the world needs (colliders, meshes, snap points, animations, lights, sounds) goes
    # to data/catalog_<n>.lua, one per menu folder (40 items at most), loaded when an item's first read (init.lua): the
    # menu and startup see only catalog.lua (was 22 MB and 130 MB of Lua heap with all of it)
    # Cyberpunk's own pieces (user, 2026-10-01): Fallout's build the settlement, so its buildings, building kits and
    # roads stay out of the menu (placed ones still load); its props, weapons and nature go in one tab of their own,
    # each kind a folder - all of them (user, 2026-10-02: "as long as the items and folders are valid, they are fair
    # game": no cap a folder, no one-a-family). Thin props against their origin hang on a wall, ones below it from a
    # ceiling; plants and rocks never do.
    for r in rows:
        if r.get('fo4') or r.get('npc') or r['cat'] == 'People': continue
        if r['cat'] in NATIVE_OUT or DUP_GUNS.match(r['key']):
            r['stashed'] = True; continue                       # (only with HS_NATIVE)
        if r.get('min') and r.get('base') and r['min'][2] < r['base'][2] - 0.01 and not BURIED.search(r['name']):
            r['base'] = [r['base'][0], r['base'][1], round(r['min'][2], 3)]   # (on its bottom, not sunk by what's under its origin)
        if r['cat'] in NATIVE_MOUNTS and not r.get('mount') and r.get('min'):
            m = native_mount(r['min'], r['max'], r['key'])
            if m: r['mount'] = m
        r['group'] = r['cat'] + '/' + r.get('group', 'Other')
        r['cat'] = NATIVE_TAB
    thumbs(rows, fo4_all)
    same = collections.defaultdict(list)                    # names: repeats among a folder's shown props get A, B, C
    for r in rows:
        if r['key'].startswith('h_') and r['cat'] == NATIVE_TAB and not r.get('stashed'): same[(r['group'], r['name'])].append(r)
    for v in same.values():
        if len(v) > 1:
            for n, r in enumerate(sorted(v, key=lambda r: r['key'])): r['name'] += ' ' + (chr(65 + n) if n < 26 else str(n))
    for r in rows:                                          # LiveNav walks a piece's box tops (livenav.lua walkTop): these
        if r['cat'] in WALK_TABS: r['walk'] = True          # tabs, and what Fallout walks or has a stair ramp (above)
    navfiles(rows)
    HEAVY = ('boxes', 'cboxes', 'pcol', 'anim', 'connect', 'meshes', 'ents', 'lights', 'fx', 'snd', 'seats', 'profile')
    for r in rows:
        r['nmesh'], r['nent'] = len(r.get('meshes') or []), len(r.get('ents') or [])
    folders, chunks = {}, []
    for r in rows:
        if not any(r.get(k) is not None for k in HEAVY): continue
        c = folders.get((r['cat'], r.get('group')))
        if c is None or len(chunks[c]) >= 40:
            chunks.append([]); c = folders[(r['cat'], r.get('group'))] = len(chunks) - 1
        chunks[c].append(r)
        r['dat'] = c + 1
    dd = os.path.join(os.path.dirname(OUT), 'data')
    os.makedirs(dd, exist_ok=True)
    for old in glob.glob(os.path.join(dd, 'catalog_*.lua')) + glob.glob(os.path.join(os.path.dirname(OUT), 'catalog_*.lua')): os.remove(old)
    for n, rs in enumerate(chunks, 1):
        with open(os.path.join(dd, 'catalog_%d.lua' % n), 'w', newline='\n', encoding='utf-8') as f:
            f.write('-- Generated by tools/build_catalog.py: the heavy half of catalog.lua items (dat = %d)\nlocal d = {}\n' % n)
            for r in rs:                                        # (a function each: LuaJIT's 65536 constants a function)
                f.write('d[%s] = (function() return %s end)()\n' % (lua(r['key']), lua({k: r.pop(k) for k in HEAVY if r.get(k) is not None})))
            f.write('return d\n')                               # (a HEAVY field left in a row is None: lua() skips it)
    with open(OUT, 'w', newline='\n', encoding='utf-8') as f:            # (names in any script: "Mateusz Łuczak")
        f.write('-- Generated by tools/build_catalog.py; edit ITEMS there. Mesh space: Z up, min/max = bounds (back included),\n')
        f.write('-- face = a wall\'s outer plane (local Y); dat = the catalog_<n>.lua with its heavy fields (boxes, meshes...).\n')
        f.write('local items = {}\n')
        for i in range(0, len(rows), 200):                  # (200 a function: LuaJIT's 65536 constants a function)
            f.write(';(function()\n')
            for r in rows[i:i + 200]: f.write('    items[#items + 1] = %s\n' % lua(r))
            f.write('end)()\n')
        f.write('local paths = {\n}\n')                     # (empty since copied buildings went; init.lua still reads
                                                            # it - goes when that does)
        sp = os.path.join(hpaths.work(), 'fo4', 'sfx', 'sounds.json')           # Fallout's sounds (tools/fo4/sounds.py)
        f.write('return { categories = %s, items = items, paths = paths, sounds = %s }\n'
                % (lua(CATS), lua(json.load(open(sp)) if os.path.exists(sp) else {})))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
