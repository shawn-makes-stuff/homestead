"""<work>/json/homestead/empty.ent.json: an empty gameObject template (one targeting component), and empty_lit.ent.json
(the same with two lights). Every Homestead piece spawns from one; the CET mod adds the mesh and collider components on
Entity/Initialize. main() writes them (tools/import.py: before the weapons, whose template is a copy, and the archive).
  python tools/make_ent.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
IDENT = {'$type': 'Quaternion', 'i': 0, 'j': 0, 'k': 0, 'r': 1}
ZERO = {'$type': 'WorldPosition', **{a: {'$type': 'FixedPoint', 'Bits': 0} for a in 'xyz'}}
CRUID = '5810274981337241857'
target = {'$type': 'gameTargetingComponent', 'aimAssistData': [], 'alwaysInTestRange': 0, 'id': CRUID, 'isDirectional': 0,
          'isEnabled': 1, 'isPrimary': 1, 'isReplicable': 0,
          'localTransform': {'$type': 'WorldTransform', 'Orientation': IDENT, 'Position': ZERO},
          'name': {'$type': 'CName', '$storage': 'string', '$value': 'Component'}, 'parentTransform': None}
root = {'$type': 'gameObject', 'customCameraTarget': 'ECCTV_All', 'renderSceneLayerMask': 'Default',
        'tags': {'$type': 'redTagList', 'tags': []}, 'visibilityCheckDistance': 16000}
ent = {'Header': {'WolvenKitVersion': '9.0.1', 'WKitJsonVersion': '0.0.9', 'GameVersion': 2310, 'DataType': 'CR2W'},
       'Data': {'Version': 195, 'BuildVersion': 0, 'RootChunk': {
           '$type': 'entEntityTemplate', 'appearances': [], 'backendDataOverrides': [], 'bindingOverrides': [],
           'compiledData': {'BufferId': '0', 'Flags': 4063232, 'Type': 'WolvenKit.RED4.Archive.Buffer.RedPackage, WolvenKit.RED4, Version=9.0.1.0, Culture=neutral, PublicKeyToken=null',
                            'Data': {'Version': 4, 'Sections': 6, 'CruidIndex': 0, 'CruidDict': {'0': '0', '1': CRUID}, 'Chunks': [root, target]}},
           'compiledEntityLODFlags': 0, 'componentResolveSettings': [], 'components': [target], 'cookingPlatform': 'PLATFORM_PC',
           'defaultAppearance': {'$type': 'CName', '$storage': 'string', '$value': 'None'},
           'entity': {'HandleId': '0', 'Data': root}, 'includeInstanceBuffer': None, 'includes': [], 'inplaceResources': [],
           'localData': None, 'resolvedDependencies': [], 'visualTagsSchema': None}, 'EmbeddedFiles': []}}
# empty_lit.ent: the same with two point lights, their settings the game's own (a Japanese lantern's light component:
# all light channels, lumens, inverse-square falloff, diffuse on transparents and particles) - a light made in Lua
# left its channels empty and lit nothing. Pieces with lights spawn from it; Lua sets colour, radius, intensity and
# where each sits (init.lua addLight).
def cname(v): return {'$type': 'CName', '$storage': 'string', '$value': v}
def light(name, cruid):
    return {'$type': 'gameLightComponent', 'allowDistantLight': 0, 'areaRectSideA': 1, 'areaRectSideB': 1, 'areaShape': 'ALS_Capsule',
            'areaTwoSided': 1, 'attenuation': 'LA_InverseSquare', 'autoHideDistance': 40, 'autoHideRange': 0, 'capsuleLength': 1,
            'clampAttenuation': 1, 'colliderName': cname('None'), 'colliderTag': cname('None'),
            'color': {'$type': 'Color', 'Alpha': 255, 'Blue': 84, 'Green': 104, 'Red': 255}, 'colorGroupSaturation': 100,
            'contactShadows': 'CSR_None', 'destructionEffect': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'uint64', '$value': '0'}, 'Flags': 'Soft'},
            'directional': 0, 'emissiveOnly': 0, 'enableContactShadows': 0, 'enableLocalShadows': 0, 'enableLocalShadowsForceStaticsOnly': 0,
            'enableShadowAngleControl': 0, 'envColorGroup': 'ECG_Default', 'EV': 0,
            'flicker': {'$type': 'rendSLightFlickering', 'flickerPeriod': 0.2, 'flickerStrength': 0, 'positionOffset': 0},
            'forceLODLevel': -1, 'genericCurveSetOverride': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'uint64', '$value': '0'}, 'Flags': 'Default'},
            'group': 'LG_Group0', 'id': cruid, 'iesProfile': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'uint64', '$value': '0'}, 'Flags': 'Soft'},
            'initialTransform': None, 'innerAngle': 30, 'intensity': 40, 'isDestructible': 0, 'isEnabled': 1, 'isReplicable': 0,
            'lightChannel': 'LC_Channel1, LC_Channel2, LC_Channel3, LC_Channel4, LC_Channel5, LC_Channel6, LC_Channel7, LC_Channel8, LC_ChannelWorld',
            'localTransform': {'$type': 'WorldTransform', 'Orientation': IDENT, 'Position': ZERO},
            'loopCurve': cname('None'), 'loopTime': 0, 'materialZone': 'Zero', 'meshBrokenAppearance': cname('None'), 'name': cname(name),
            'noSpecular': 0, 'onStrength': 1, 'outerAngle': 45, 'parentTransform': None, 'pathTracingLightUsage': 'PTLU_Everywhere',
            'pathTracingOverrideScaleGI': 1, 'placedEditorData': None, 'portalAngleCutoff': 0, 'radius': 2.5, 'rayTracedShadowsPlatform': 'RLSP_All',
            'rayTracingContactShadowRange': -1, 'rayTracingIntensityScale': 1, 'rayTracingLightSourceRadius': -1, 'renderSceneLayerMask': 'Default',
            'roughnessBias': 50, 'rtxdiShadowStartingDistance': -1, 'scaleEnvProbes': 0, 'scaleGI': 0, 'scaleVolFog': 0, 'sceneDiffuse': 1,
            'sceneSpecular': 0, 'sceneSpecularScale': 100, 'shadowAngle': -1, 'shadowFadeDistance': 10, 'shadowFadeRange': 5, 'shadowRadius': -1,
            'shadowSoftnessMode': 'LSSM_Default', 'softness': 2, 'sourceRadius': 0.05, 'spotCapsule': 0, 'synchronizedLoop': 0, 'temperature': -1,
            'turnOffCurve': cname('None'), 'turnOffTime': 0.3, 'turnOnByDefault': 1, 'turnOnCurve': cname('None'), 'turnOnTime': 0.3,
            'type': 'LT_Point', 'unit': 'LU_Lumen', 'useInEnvProbes': 0, 'useInFog': 0, 'useInGI': 0, 'useInParticles': 1, 'useInTransparents': 1}
import copy
lit = copy.deepcopy(ent)
L = [light('hs_light1', '5810274981337241858'), light('hs_light2', '5810274981337241859')]
rc = lit['Data']['RootChunk']
rc['components'] = rc['components'] + L
rc['compiledData']['Data']['Chunks'] = rc['compiledData']['Data']['Chunks'] + L
rc['compiledData']['Data']['CruidDict'] = {'0': '0', '1': CRUID, '2': L[0]['id'], '3': L[1]['id']}


def main():
    for name, doc in (('empty.ent.json', ent), ('empty_lit.ent.json', lit)):
        out = os.path.join(paths.work(), 'json', 'homestead', name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        json.dump(doc, open(out, 'w'), indent=1)
        print(out)


if __name__ == '__main__':
    main()
