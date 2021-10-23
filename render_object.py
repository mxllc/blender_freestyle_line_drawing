'''
Render multi-view image for object without texture

Support for rgb, depth, normal
'''
from multiprocessing import Pool, Process
import argparse, sys, os, time
import logging
import numpy as np
import math
from math import radians

# logging.basicConfig(filename='log.txt',level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
import bpy
import pdb

# render main function
def render_function(model_dir):
    ### setting
    bpy.context.scene.use_nodes = True
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.render.line_thickness_mode = 'ABSOLUTE'
    bpy.context.scene.render.line_thickness = 0.1
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    # print(dir(bpy.context.scene.render))
    # input('debugs')
    tree = bpy.context.scene.node_tree
    links = tree.links

    # bpy.context.scene.render.layers["RenderLayer"].use_freestyle = True
    # Add passes for additionally dumping albedo and normals.
    # bpy.context.scene.render.layers["RenderLayer"].use_pass_normal = True
    # # bpy.context.scene.render.layers["RenderLayer"].use_pass_color = True
    # bpy.context.scene.render.layers["RenderLayer"].use_pass_environment = True
    # bpy.context.scene.render.layers["RenderLayer"].use_pass_z = True

    bpy.context.scene.view_layers["View Layer"].use_pass_normal = True
    bpy.context.scene.view_layers["View Layer"].use_pass_environment = True
    bpy.context.scene.view_layers["View Layer"].use_pass_z = True
    bpy.context.scene.view_layers["View Layer"].use_freestyle = True
    bpy.context.scene.view_layers["View Layer"].freestyle_settings.use_suggestive_contours = True
    bpy.context.scene.view_layers["View Layer"].freestyle_settings.as_render_pass = True
    
    # bpy.context.scene.cycles.device = 'GPU'
    # bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
    # bpy.context.preferences.addons['cycles'].preferences.compute_device = 'CUDA_0'
    # for devices in bpy.context.preferences.addons['cycles'].preferences.get_devices():
    #     for d in devices:
    #         d.use = True
    #         if d.type == 'CPU':
    #             d.use = False

    # bpy.context.scene.view_layers["View Layer"].freestyle_settings.linesets.exclude_silhouette = True
    # print(dir(bpy.context.scene.view_layers["View Layer"].freestyle_settings.linesets))
    # input('debug')
    # print(bpy.context.scene.view_layers["View Layer"].freestyle_settings.use_suggestive_contours)
    # input('debug')
    
    bpy.context.scene.render.image_settings.file_format = args.format
    bpy.context.scene.render.image_settings.color_depth = args.color_depth

    # bpy.types.FreestyleSettings.use_suggestive_contours = True
    # Clear default nodes
    for n in tree.nodes:
        tree.nodes.remove(n)

    # Create input render layer node.
    render_layers = tree.nodes.new('CompositorNodeRLayers')

    depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    depth_file_output.label = 'Depth Output'
    if args.format == 'OPEN_EXR':
        links.new(render_layers.outputs['Depth'], depth_file_output.inputs[0])
    else:
        # Remap as other types can not represent the full range of depth.
        normalize = tree.nodes.new(type="CompositorNodeNormalize")
        links.new(render_layers.outputs['Depth'], normalize.inputs[0])
        links.new(normalize.outputs[0], depth_file_output.inputs[0])

    scale_normal = tree.nodes.new(type="CompositorNodeMixRGB")
    scale_normal.blend_type = 'MULTIPLY'
    # scale_normal.use_alpha = True
    scale_normal.inputs[2].default_value = (0.5, 0.5, 0.5, 1)
    links.new(render_layers.outputs['Normal'], scale_normal.inputs[1])

    bias_normal = tree.nodes.new(type="CompositorNodeMixRGB")
    bias_normal.blend_type = 'ADD'
    # bias_normal.use_alpha = True
    bias_normal.inputs[2].default_value = (0.5, 0.5, 0.5, 0)
    links.new(scale_normal.outputs[0], bias_normal.inputs[1])

    normal_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    normal_file_output.label = 'Normal Output'
    links.new(bias_normal.outputs[0], normal_file_output.inputs[0])

    albedo_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    albedo_file_output.label = 'Albedo Output'
    links.new(render_layers.outputs['Env'], albedo_file_output.inputs[0])

    sc_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    sc_file_output.label = 'Suggestive Contours Output'
    links.new(render_layers.outputs['Alpha'], sc_file_output.inputs[0])

    # print(render_layers.outputs.keys())
    # input('debug')
    fs_output = tree.nodes.new(type="CompositorNodeOutputFile")
    fs_output.label = 'Frestyle Output'
    links.new(render_layers.outputs['Freestyle'], fs_output.inputs[0])


    # mix_freestyle = tree.nodes.new(type="CompositorNodeMixRGB")
    # mix_freestyle.blend_type = 'MIX'
    # mix_freestyle.use_alpha = True
    # mix_freestyle.label = 'Suggestive Contours Output hh'
    # links.new(render_layers.outputs['hh'], hh_output.inputs[0])


    # # Delete default cube
    # bpy.data.objects['Cube'].select = True
    # bpy.ops.object.delete()
    # bpy.data.objects['Lamp'].select = True
    # bpy.ops.object.delete()

    # Delete default cube
    bpy.context.active_object.select_set(True)
    bpy.ops.object.delete()
    

    ## render
    # model_ids = os.listdir(model_dir)
    # model_ids = os.listdir(model_dir)[::-1]
    # model_ids = os.listdir(model_dir)[8000:8500]
    # model_ids = os.listdir(model_dir)[8500:9000]
    # model_ids = os.listdir(model_dir)[8500:]
    # model_ids = ['M001361.obj', 'M002909.obj', 'M000001.obj', 'M000002.obj', 'M000003.obj', 'M000022.obj', 'M000015.obj', 'M003339.obj']
    for index, model_id in enumerate(model_ids):
        model_id = model_id.split('.')[0]
        if os.path.exists(os.path.join(args.output_folder, model_id)):
            continue
        else:
            obj_file = os.path.join(model_dir, model_id+'.obj')
            try: bpy.ops.import_scene.obj(filepath=obj_file)
            except: continue
            
            # bpy.context.scene.render.engine = 'BLENDER_EEVEE'

            # for object in bpy.context.scene.objects:
            #     print(object.name)
            #     # print('***debug***')
            #     # print(dir(object))
            #     if object.name in ['Camera']:
            #         object.select = False
            #     else:
            #         object.select = False
            #         object.cycles_visibility.shadow = False

                    # for edge in object.data.edges:
                    #     edge.use_freestyle_mark = True
                    # #show the marked edges
                    # object.data.show_freestyle_edge_marks = True
            
            # input('debug:hhh')

            bpy.data.worlds['World'].use_nodes = True
            bpy.data.worlds['World'].node_tree.nodes['Background'].inputs[0].default_value[0:3] = (0.6, 0.6, 0.6)
            
            def parent_obj_to_camera(b_camera):
                origin = (0, 0, 0)
                b_empty = bpy.data.objects.new("Empty", None)
                b_empty.location = origin
                b_camera.parent = b_empty  # setup parenting

                scn = bpy.context.scene
                scn.collection.objects.link(b_empty)
                bpy.context.view_layer.objects.active = b_empty
                return b_empty

            scene = bpy.context.scene
            bpy.context.scene.cycles.samples = 20
            scene.render.resolution_x = 256 # 384
            scene.render.resolution_y = 256
            scene.render.resolution_percentage = 100
            # scene.render.alpha_mode = 'TRANSPARENT'
            scene.render.film_transparent = True
            cam = scene.objects['Camera']
            # cam.location = (0, 3.2, 0.8) # modified
            # cam.location = (0, 2.8, 0.6) # MODIFIED
            cam.location = (0, 0, 3.6) # MODIFIED
            cam.data.lens = 35
            # cam.location = (0, 0, 3.2) # MODIFIED
            # cam.data.angle = 0.9799147248268127
            cam_constraint = cam.constraints.new(type='TRACK_TO')
            cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
            cam_constraint.up_axis = 'UP_Y'
            b_empty = parent_obj_to_camera(cam)
            cam_constraint.target = b_empty

            world = bpy.data.worlds['World']
            world.light_settings.use_ambient_occlusion = True
            world.light_settings.ao_factor = 0.6
            
            fp = args.output_folder
            scene.render.image_settings.file_format = 'PNG'  # set output format to .png

            
            rotation_mode = 'XYZ'

            for output_node in [depth_file_output, normal_file_output, albedo_file_output, sc_file_output, fs_output]:
                output_node.base_path = ''

            # b_empty.rotation_euler[2] += radians(330)
            
            cur_obj = bpy.context.selected_objects[0]
            # render image by views
            pose_dict = {}

            ddir = os.path.join(args.output_folder, model_id)
            # if os.path.exists(ddir) and len(os.listdir(ddir)) == 12:
            if os.path.exists(ddir):
                for object in bpy.context.scene.objects:
                    print(object.name)
                    if object.name in ['Camera']:
                        object.select_set(False)
                        continue
                    else:
                        object.select_set(True)
                bpy.ops.object.delete()
                continue


            # some bugs in blender freestyle rendering (camera views not sync)
            # 0 -> x, 1 -> y, 2 -> z
            cur_obj.rotation_euler[0] -= radians(90)

            cur_obj.rotation_euler[0] -= radians(12)
            cur_obj.rotation_euler[1] -= radians(12)
            cur_obj.rotation_euler[2] -= radians(15)

            # v_num = args.views
            for j in range(3):
                cur_obj.rotation_euler[j] -= radians(30)
                v_num = 4
                stepsize = 360.0 / v_num   # 45 degrees
                for i in range(v_num):
                    print("Rotation {}, {}".format((stepsize * i), radians(stepsize * i)))
                    save_dir = os.path.join(args.output_folder, model_id)
                    if os.path.exists(save_dir) == False:
                        os.makedirs(save_dir)
                    
                    # scene.render.filepath = os.path.join(save_dir, 'image_' + '{0:02d}'.format(int(i * stepsize)))                              # rgb
                    # scene.render.filepath = os.path.join(save_dir, 'o'+'{0:02d}'.format(j*4+i))                            # rgb

                    # depth_file_output.file_slots[0].path = os.path.join(save_dir, 'depth_' + '{0:03d}'.format(int(i * stepsize)) + '_')         # depth
                    # normal_file_output.file_slots[0].path = os.path.join(save_dir, 'normal_' + '{0:03d}'.format(int(i * stepsize)) + '_')       # normal
                    # albedo_file_output.file_slots[0].path = os.path.join(save_dir, 'mask_' + '{0:03d}'.format(int(i * stepsize)) + '_')         # mask
                    # sc_file_output.file_slots[0].path = os.path.join(save_dir, 'sc_' + '{0:03d}'.format(int(i * stepsize)) + '_')         # sc
                    # fs_output.file_slots[0].path = os.path.join(save_dir, 'hh_' + '{0:03d}'.format(int(i * stepsize)) + '_')         # fs
                    
                    fs_output.file_slots[0].path = os.path.join(save_dir, '{0:02d}.png'.format(j*4+i))


                    bpy.ops.render.render(write_still=True)  # render still
                    # b_empty.rotation_euler[2] += radians(stepsize)
                    cur_obj.rotation_euler[j] += radians(stepsize)

                cur_obj.rotation_euler[j] += radians(30)
                # break
            
            # clear sys
            # obj = bpy.context.selected_objects[0]
            # print(obj.name)
            # print('----')
            for object in bpy.context.scene.objects:
                print(object.name)
                if object.name in ['Camera']:
                    object.select_set(False)
                    continue
                else:
                    object.select_set(True)
            bpy.ops.object.delete() 


            # input('debug')

###### render model images
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
    parser.add_argument('--views', type=int, default=12,
                        help='number of views to be rendered')
    # parser.add_argument('input_folder', type=str,
    #                     help='The path to where obj file and texture file stored')
    parser.add_argument('--output_folder', type=str, default='/render2',
                        help='The path the output will be dumped to.')
    parser.add_argument('--number_process', type=int, default=12,
                        help='number of multi-processing.')
    parser.add_argument('--scale', type=float, default=1,
                        help='Scaling factor applied to model. Depends on size of mesh.')
    parser.add_argument('--remove_doubles', type=bool, default=True,
                        help='Remove double vertices to improve mesh quality.')
    parser.add_argument('--edge_split', type=bool, default=True,
                        help='Adds edge split filter.')
    parser.add_argument('--depth_scale', type=float, default=1.0,
                        help='Scaling that is applied to depth. Depends on size of mesh. Try out various values until you get a good result. Ignored if format is OPEN_EXR.')
    parser.add_argument('--color_depth', type=str, default='8',
                        help='Number of bit per channel used for output. Either 8 or 16.')
    parser.add_argument('--format', type=str, default='PNG',
                        help='Format of files generated. Either PNG or OPEN_EXR')

    argv = sys.argv[sys.argv.index("--") + 1:]
    args = parser.parse_args(argv)

    model_dir = './data/SHREC2014/models_std'
    render_function(model_dir)
