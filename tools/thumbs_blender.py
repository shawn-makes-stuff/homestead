"""Blender (background) script: a 3/4 view render per item, textured, transparent background - the menu's thumbnails.
blender -b -P tools/thumbs_blender.py -- <jobs.json> <size>
jobs.json: [[parts, png, tex, view], ...]: parts = [[glb, x, y, z, yaw] or [glb, x, y, z, yaw, [i, j, k, r], [sx, sy, sz],
chunk mask (bit n off: submesh n left out)]], tex = {glb: {material: [colour png or null (glass: pale), alpha threshold or
null(, opacity)]}} - a material with no entry renders light grey. view: None, 'flip' (a sign seen from its other
side), 'person' (from the front, head and chest), 'side' (a weapon: side on).
Night City's glbs share one material ("Default") over all their submeshes: theirs go by submesh ("submesh_NN",
tools/nc_textures.py), each submesh given its own copy of the material, named so.
"""
import bpy, json, math, re, sys
import numpy as np
from mathutils import Vector, Quaternion, Matrix

args = sys.argv[sys.argv.index('--') + 1:]
jobs, size = json.load(open(args[0])), int(args[1])
scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.render.resolution_x = scn.render.resolution_y = size
scn.render.film_transparent = True
scn.render.image_settings.color_mode = 'RGBA'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'TEXTURE'              # the material's image; none: its base colour
scn.display.shading.show_cavity = True
scn.display.shading.show_object_outline = False
scn.display.shading.show_shadows = False
scn.view_settings.view_transform = 'Standard'
IMG = {}


def dress(objs, tex):                                       # each material: its colour texture (and alpha cut-out)
    for o in objs:
        sub = re.match(r'submesh_\d+', o.data.name)
        if sub and sub.group() in tex and o.material_slots and o.material_slots[0].material:
            m = o.material_slots[0].material.copy()          # (Night City's: by submesh)
            m.name = sub.group()
            o.material_slots[0].material = m
    for o in objs:
        for sl in o.material_slots:
            m = sl.material
            if not m or m.get('hs'): continue
            m['hs'] = 1
            m.use_nodes = True
            nt = m.node_tree
            for n in [n for n in nt.nodes if n.type == 'TEX_IMAGE']: nt.nodes.remove(n)
            bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if not bsdf: continue
            t = tex.get(re.sub(r'\.\d{3}$', '', m.name))
            if len(t or []) > 2 and t[2]: m.diffuse_color[3] = t[2]   # (see-through: Workbench takes the material's alpha)
            if not t or not t[0]:
                c = (0.62, 0.62, 0.62) if not t else (0.8, 0.88, 0.92)
                bsdf.inputs['Base Color'].default_value = (*c, 1)
                m.diffuse_color[:3] = c
                continue
            if (t[0], t[1]) not in IMG:
                img = IMG[t[0], t[1]] = bpy.data.images.load(t[0], check_existing=False)
                if t[1] is not None:                         # (cut here, at the material's threshold: Workbench cuts at its own)
                    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
                    img.pixels.foreach_get(px)
                    px[3::4] = px[3::4] >= float(t[1])
                    img.pixels.foreach_set(px)
            node = nt.nodes.new('ShaderNodeTexImage'); node.image = IMG[t[0], t[1]]
            nt.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
            if t[1] is not None:
                nt.links.new(node.outputs['Alpha'], bsdf.inputs['Alpha'])
                m.blend_method, m.alpha_threshold = 'CLIP', float(t[1])
            nt.nodes.active = node                           # (Workbench's TEXTURE colour reads the active image)


def faces_back(objs, lo, hi):
    """a flat piece facing +Y - standing out of its wall (y = 0) that way, or its faces mostly pointing so (area-weighted
    normals): its printed side away from the camera"""
    size = hi - lo
    if size.y > 0.3 * max(size.x, size.z): return False
    if lo.y > -0.02 and hi.y > 0.05: return True
    ny = area = 0.0
    for o in objs:
        rot = o.matrix_world.to_3x3()
        for p in o.data.polygons:
            ny += (rot @ p.normal).y * p.area; area += p.area
    return ny > 0.3 * area


for parts, png, tex, view in jobs:
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials): bpy.data.materials.remove(m)
    try:
        cache = {}                                          # glb -> its meshes and their node transforms, imported once
        for part in parts:
            g, x, y, z, yaw = part[:5]
            mask = part[7] if len(part) > 7 else -1
            if (g, mask) not in cache:
                before = set(bpy.data.objects)
                bpy.ops.import_scene.gltf(filepath=g)
                new = [o for o in set(bpy.data.objects) - before if o.type == 'MESH' and not o.name.startswith('Icosphere')]   # (the importer's bone shape)
                dress(new, tex.get(g, {}))
                cache[g, mask] = [(o.data, o.matrix_world.copy()) for o in new
                                  if mask >> int((re.match(r'submesh_(\d+)', o.data.name) or [0, 0])[1]) & 1]
                for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
            if len(part) > 5 and part[5]:
                i, j, k, r = part[5]
                rotm = Quaternion((r, i, j, k)).to_matrix().to_4x4()
            else:
                rotm = Matrix.Rotation(math.radians(yaw), 4, 'Z')
            scm = Matrix.Diagonal((part[6][0], part[6][1], part[6][2], 1.0)) if len(part) > 6 and part[6] else Matrix.Identity(4)
            place = Matrix.Translation((x, y, z)) @ rotm @ scm
            for mesh, mw in cache[g, mask]:
                o = bpy.data.objects.new('p', mesh)
                scn.collection.objects.link(o)
                o.matrix_world = place @ mw
        bpy.context.view_layer.update()
    except Exception:
        continue
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    if not objs: continue
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scn.collection.objects.link(cam); scn.camera = cam
    d = Vector((1.0, -1.3, 0.9))
    if (any(k.startswith('submesh_') for t in tex.values() for k in t) and faces_back(objs, lo, hi)) != (view == 'flip'):
        d = Vector((-1.0, 1.3, 0.9))                        # (a Night City sign or poster faces +Y: seen from its front)
    if view == 'side': d = Vector((1.0, -0.35, 0.3))
    if view == 'person':                                    # (a person faces +Y; one of a person's height: head and chest)
        d = Vector((-0.5, 1.0, 0.12))
        if 1.3 < hi.z - lo.z < 2.4 and hi.x - lo.x < 2.2:
            w = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
            top = [p for p in w if p.z > hi.z - 0.62]
            lo = Vector((max(min(p.x for p in top), -0.33), min(p.y for p in top), hi.z - 0.62))
            hi = Vector((min(max(p.x for p in top), 0.33), max(p.y for p in top), hi.z))
    d = d.normalized()
    c, r = (lo + hi) / 2, max((hi - lo).length / 2, 0.01)
    cam.location = c + d * r * 4
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO'
    right = (cam.rotation_euler.to_matrix() @ Vector((1, 0, 0)))   # fit: the bounds' corners projected on the view plane
    up = (cam.rotation_euler.to_matrix() @ Vector((0, 1, 0)))
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    w = max(abs((q - c).dot(right)) for q in corners) * 2
    h = max(abs((q - c).dot(up)) for q in corners) * 2
    cam.data.ortho_scale = max(w, h) * 1.12
    cam.data.clip_end = r * 10 + 10
    scn.render.filepath = png
    bpy.ops.render.render(write_still=True)
