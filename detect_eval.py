"""
Normalized Object Coordinate Space for Category-Level 6D Object Pose and Size Estimation
Detection and evaluation

Modified based on Mask R-CNN(https://github.com/matterport/Mask_RCNN)
Written by He Wang
"""

import os
import argparse
import xlwt 
from xlwt import Workbook 
import numpy as np
import math
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation as R
parser = argparse.ArgumentParser()
parser.add_argument('--mode', default='detect', type=str, help="detect/eval")
parser.add_argument('--use_regression', dest='use_regression', action='store_true')
parser.add_argument('--use_delta', dest='use_delta', action='store_true')
#parser.add_argument('--ckpt_path', type=str, default='logs/final/mask_rcnn_shapenettoi_0020.h5')
#parser.add_argument('--ckpt_path', type=str, default='logs/nocs_rcnn_res50_regression.h5')
#parser.add_argument('--ckpt_path', type=str, default='logs/FINAL/final/mask_rcnn_shapenettoi_0070.h5')
#parser.add_argument('--ckpt_path', type=str, default='logs/shapenettoi20200711T0801_scale_depth_corrected140/mask_rcnn_shapenettoi_0070.h5')
#parser.add_argument('--ckpt_path', type=str, default='logs/shapenettoi20200709T0116_depth_corrected_laplace/mask_rcnn_shapenettoi_0070.h5')
#parser.add_argument('--ckpt_path', type=str, default='logs/shapenettoi20200704T0428_large_dataset_fine_tuned_100_40_70/mask_rcnn_shapenettoi_0070.h5')
parser.add_argument('--ckpt_path', type=str, default='logs/shapenettoi20200713T0857_largest_dataset_250/mask_rcnn_shapenettoi_0250.h5')
parser.add_argument('--data', type=str, help="val/real_test", default='real_test')
parser.add_argument('--gpu',  default='0', type=str)
parser.add_argument('--draw', dest='draw', action='store_true', help="whether draw and save detection visualization")
parser.add_argument('--num_eval', type=int, default=-1)

parser.set_defaults(use_regression=False)
#parser.set_defaults(draw=False)
parser.set_defaults(draw=True)
parser.set_defaults(use_delta=False)
args = parser.parse_args()

mode = args.mode
data = args.data
ckpt_path = args.ckpt_path
use_regression = args.use_regression
use_delta = args.use_delta
num_eval = args.num_eval

os.environ['CUDA_VISIBLE_DEVICES']=args.gpu
print('Using GPU {}.'.format(args.gpu))

import sys
import datetime
import glob
import time
import numpy as np
from config import Config
import utils
import model as modellib
from dataset import NOCSDataset
import _pickle as cPickle
from train import ScenesConfig

# Root directory of the project
ROOT_DIR = os.getcwd()

# Directory to save logs and trained model
MODEL_DIR = os.path.join(ROOT_DIR, "logs")

# Path to COCO trained weights
COCO_MODEL_PATH = os.path.join(MODEL_DIR, "mask_rcnn_coco.h5")


class InferenceConfig(ScenesConfig):
    """Configuration for training on the toy shapes dataset.
    Derives from the base Config class and overrides values specific
    to the toy shapes dataset.
    """
    # Give the configuration a recognizable name
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1

    COORD_USE_REGRESSION = use_regression
    if COORD_USE_REGRESSION:
        COORD_REGRESS_LOSS   = 'Soft_L1' 
    else:
        COORD_NUM_BINS = 32
    COORD_USE_DELTA = use_delta

    USE_SYMMETRY_LOSS = True
    TRAINING_AUGMENTATION = False



if __name__ == '__main__':

    config = InferenceConfig()
    config.display()

    # Training dataset
    # dataset directories
    #camera_dir = os.path.join('data', 'camera')
    real_dir = os.path.join('data', 'real')
    coco_dir = os.path.join('data', 'coco')
    hand_dir = os.path.join('data','hand_scale_test_depth_corrected')
    #hand_dir = os.path.join('data','hand_dataset')
    #  real classes
    coco_names = ['BG', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
                  'bus', 'train', 'truck', 'boat', 'traffic light',
                  'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird',
                  'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear',
                  'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie',
                  'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
                  'kite', 'baseball bat', 'baseball glove', 'skateboard',
                  'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
                  'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
                  'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
                  'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
                  'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
                  'keyboard', 'cell phone', 'microwave', 'oven', 'toaster',
                  'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
                  'teddy bear', 'hair drier', 'toothbrush','hand']

    
    synset_names = ['BG', #0
                    'bottle', #1
                    'bowl', #2
                    'camera', #3
                    'can',  #4
                    'laptop',#5
                    'mug',#6
                    'hand'
                    ]

    class_map = {
        'bottle': 'bottle',
        'bowl':'bowl',
        'cup':'mug',
        'laptop': 'laptop',
        'baseball glove':'hand'
    }


    coco_cls_ids = []
    for coco_cls in class_map:
        ind = coco_names.index(coco_cls)
        coco_cls_ids.append(ind)
    config.display()

    assert mode in ['detect', 'eval']
    if mode == 'detect':
        # Recreate the model in inference mode
        model = modellib.MaskRCNN(mode="inference",
                                  config=config,
                                  model_dir=MODEL_DIR)

        gt_dir = os.path.join('data','gts', data)
        
       
        if data == 'val':
            dataset_val = NOCSDataset(synset_names, 'val', config)
            dataset_val.load_camera_scenes(camera_dir)
            dataset_val.prepare(class_map)
            dataset = dataset_val
        if data == 'real_test':
            dataset_real_test = NOCSDataset(synset_names, 'test', config)
            dataset_real_test.load_real_scenes(hand_dir)
            dataset_real_test.prepare(class_map)
            dataset = dataset_real_test
            
        else:
            assert False, "Unknown data resource."
            
        

        # Load trained weights (fill in path to trained weights here)
        model_path = ckpt_path
        assert model_path != "", "Provide path to trained weights"
        print("Loading weights from ", model_path)
        model.load_weights(model_path, by_name=True)


        image_ids = dataset.image_ids
        save_per_images = 10
        now = datetime.datetime.now()
        save_dir = os.path.join('output', "{}_{:%Y%m%dT%H%M}".format(data, now))
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        log_file = os.path.join(save_dir, 'error_log.txt')
        f_log = open(log_file, 'w')
        
        T_file = os.path.join(save_dir, 'translation.txt')
        T_log = open(T_file, 'w')
        R_file = os.path.join(save_dir, 'rotation.txt')
        R_log = open(R_file, 'w')
        
        wb = Workbook() 
        sheet1 = wb.add_sheet('Sheet 1') 
        sheet1.write(0, 0, 'TRANSLATION') 
        sheet2 = wb.add_sheet('Sheet 2') 
        sheet2.write(0, 0, 'ROTATION') 
        
        ################## WRONG
        
        def rotation_to_euler(Rot):
            r = R.from_matrix(Rot)
            x,y,z = r.as_euler('zyx',degrees=True)
            '''
            y = -math.asin(R[2,0]) *180/3.14
            x = math.atan(R[2,1]/R[2,2]) *180/3.14
            z = math.atan(R[1,0]/R[0,0]) *180/3.14
               ''' 
            return x,y,z  
            
        '''
        def rotation_to_euler(R):
            x = math.atan(R[2,1]/-R[2,0]) *180/3.14
            y = -math.acos(R[2,2]) *180/3.14
            z = math.atan(R[1,2]/R[0,2]) *180/3.14

            return x,y,z
         '''
        #hand dataset blender
        #intrinsics = np.array([[700, 0, 520], [0, 933.333, 250], [0, 0, 1]])
        
        intrinsics = np.array([[700, 0, 320], [0, 933.3333, 240], [0, 0, 1]])
        '''
        if data in ['real_train', 'real_test']:
            intrinsics = np.array([[591.0125, 0, 322.525], [0, 590.16775, 244.11084], [0, 0, 1]])
        
        else: ## CAMERA data
            intrinsics = np.array([[577.5, 0, 319.5], [0., 577.5, 239.5], [0., 0., 1.]])
         '''
        elapse_times = []
        if mode != 'eval':
            for i, image_id in enumerate(image_ids):
                i=i
                image_id=i
                print('*'*50)
                image_start = time.time()
                print('Image id: ', image_id)
                image_path = dataset.image_info[image_id]["path"]
                print(image_path)

    
                # record results
                result = {}
                
                # loading ground truth
                image = dataset.load_image(image_id)
                depth = dataset.load_depth(image_id)
                
                gt_mask, gt_coord, gt_class_ids, gt_scales, gt_domain_label = dataset.load_mask(image_id)
                
                #for_hand
                #gt_scales=np.array([[0.125,0.9,0.6]])
                #gt_scales=np.array([[0.1644,0.541,1]])
                gt_bbox = utils.extract_bboxes(gt_mask)
     
                result['image_id'] = image_id
                result['image_path'] = image_path

                result['gt_class_ids'] = gt_class_ids
                result['gt_bboxes'] = gt_bbox
                result['gt_RTs'] = None            
                result['gt_scales'] = gt_scales
                result['gt_rotation'] =None
                result['gt_translation'] = None
                
                image_path_parsing = image_path.split('/')
                gt_pkl_path = os.path.join(gt_dir, 'results_{}_{}_{}.pkl'.format(data, image_path_parsing[-2], image_path_parsing[-1]))
                print(gt_pkl_path)
                if (os.path.exists(gt_pkl_path)):
                    with open(gt_pkl_path, 'rb') as f:
                        gt = cPickle.load(f)
                    result['gt_RTs'] = gt['gt_RTs']
                    if 'handle_visibility' in gt:
                        result['gt_handle_visibility'] = gt['handle_visibility']
                        assert len(gt['handle_visibility']) == len(gt_class_ids)
                        print('got handle visibiity.')
                    else: 
                        result['gt_handle_visibility'] = np.ones_like(gt_class_ids)
                else:
            # align gt coord with depth to get RT
                    if not data in ['coco_val', 'coco_train']:
                        if len(gt_class_ids) == 0:
                            print('No gt instance exsits in this image.')

                        print('\nAligning ground truth...')
                        start = time.time()
                        result['gt_RTs'], _, error_message, _, result['gt_rotation'], result['gt_translation'] = utils.align(gt_class_ids, 
                                                                         gt_mask, 
                                                                         gt_coord, 
                                                                         depth, 
                                                                         intrinsics, 
                                                                         synset_names, 
                                                                         image_path,
                                                                         save_dir+'/'+'{}_{}_{}_gt_'.format(data, image_path_parsing[-2], image_path_parsing[-1]))
                        print('New alignment takes {:03f}s.'.format(time.time() - start))
                
                        #print('gt_RTs',result['gt_RTs'])
                        
                        if len(error_message):
                            f_log.write(error_message)

                    result['gt_handle_visibility'] = np.ones_like(gt_class_ids)
                 
                ## detection
                start = time.time()
                detect_result = model.detect([image], verbose=0)
                r = detect_result[0]
                elapsed = time.time() - start
                
                print('\nDetection takes {:03f}s.'.format(elapsed))
                result['pred_class_ids'] = r['class_ids']
                result['pred_bboxes'] = r['rois']
                result['pred_RTs'] = None   
                result['pred_scores'] = r['scores']
                result['pred_rotation'] = None
                result['pred_translation'] =None
                print('gt_class ',gt_class_ids,' pred_class ', result['pred_class_ids'])
                
                if len(r['class_ids']) == 0:
                    print('No instance is detected.')

                print('Aligning predictions...')
                start = time.time()
                result['pred_RTs'], result['pred_scales'], error_message, elapses, result['pred_rotation'], result['pred_translation'] =  utils.align(r['class_ids'], 
                                                                                        r['masks'], 
                                                                                        r['coords'], 
                                                                                        depth, 
                                                                                        intrinsics, 
                                                                                        synset_names, 
                                                                                        image_path,
                
                                                                                        save_dir+'/'+'{}_{}_{}_pred_'.format(data, image_path_parsing[-2], image_path_parsing[-1]))
                
                print('New alignment takes {:03f}s.'.format(time.time() - start))
                elapse_times += elapses
                if len(error_message):
                    f_log.write(error_message)

                #FINDING OUT THE TRANSLATION AND ROTATION FOR EACH IMAGE
                T_log = open(T_file, 'a+')
                T_log.write('{} {} '.format(str(result['gt_translation'][np.where(gt_class_ids==7)][0][0]),str(result['pred_translation'][np.where(result['pred_class_ids']==7)][0][0])))
                T_log.write('{} {} '.format(str(result['gt_translation'][np.where(gt_class_ids==7)][0][1]),str(result['pred_translation'][np.where(result['pred_class_ids']==7)][0][1])))
                T_log.write('{} {}\n'.format(str(result['gt_translation'][np.where(gt_class_ids==7)][0][2]),str(result['pred_translation'][np.where(result['pred_class_ids']==7)][0][2])))

                #T_log.write(str(np.abs(result['gt_translation'][np.where(gt_class_ids==7)][0][2]-result['pred_translation'][np.where(result['pred_class_ids']==7)][0][2]))+'\n')
                #sheet1.write(i+1, 0, np.linalg.norm(result['gt_RTs'][0,:,-1]-result['pred_RTs'][0,:,-1])) 
                
                R_gt = result['gt_rotation'][np.where(gt_class_ids==7)][0]
                R_pred = result['pred_rotation'][np.where(gt_class_ids==7)][0]
                
                #print('R_gt',R_gt)
                '''
                R_gt = result['gt_RTs'][np.where(gt_class_ids==7)][0][:3,:3]
                R_pred = result['pred_RTs'][np.where(gt_class_ids==7)][0][:3,:3]
                '''
                theta_x_gt, theta_y_gt, theta_z_gt = rotation_to_euler(R_gt)
                theta_x_pred, theta_y_pred, theta_z_pred = rotation_to_euler(R_pred)
                R_log = open(R_file, 'a+')
                R_log.write('{} {} {} {} {} {}\n'.format(str(theta_x_gt),str(theta_x_pred),str(theta_y_gt),str(theta_y_pred),str(theta_z_gt),str(theta_z_pred)))
                T_log.close()
                R_log.close()                
                #sheet2.write(i+1, 0, (theta_x_gt -theta_x_pred)*180/3.14)
                #sheet2.write(i+1, 1, (theta_y_gt -theta_y_pred)*180/3.14)
               # sheet2.write(i+1, 2, (theta_z_gt -theta_z_pred)*180/3.14)
                
               
                
                
                
                if args.draw:
                    draw_rgb = False
                    utils.draw_detections(image, save_dir, data, image_path_parsing[-2]+'_'+image_path_parsing[-1], intrinsics, synset_names, draw_rgb,
                                            gt_bbox, gt_class_ids, gt_mask, gt_coord, result['gt_RTs'], gt_scales, result['gt_handle_visibility'],
                                            r['rois'], r['class_ids'], r['masks'], r['coords'], result['pred_RTs'], r['scores'], result['pred_scales'])
                
              

                path_parse = image_path.split('/')
                image_short_path = '_'.join(path_parse[-3:])

                save_path = os.path.join(save_dir, 'results_{}.pkl'.format(image_short_path))
                with open(save_path, 'wb') as f:
                    cPickle.dump(result, f)
                print('Results of image {} has been saved to {}.'.format(image_short_path, save_path))

                
                elapsed = time.time() - image_start
                print('Takes {} to finish this image.'.format(elapsed))
                print('Alignment average time: ', np.mean(np.array(elapse_times)))
                print('\n')
                print('gt_scales',gt_scales)
                print('pred_scales',result['pred_scales'])
            f_log.close()
            

    else:
        log_dir = 'output/real_test_20200615T1026'
    
        result_pkl_list = glob.glob(os.path.join(log_dir, 'results_*.pkl'))
        result_pkl_list = sorted(result_pkl_list)[:num_eval]
        assert len(result_pkl_list)

        final_results = []
        for pkl_path in result_pkl_list:
            with open(pkl_path, 'rb') as f:
                result = cPickle.load(f)
                if not 'gt_handle_visibility' in result:
                    result['gt_handle_visibility'] = np.ones_like(result['gt_class_ids'])
                    print('can\'t find gt_handle_visibility in the pkl.')
                else:
                    assert len(result['gt_handle_visibility']) == len(result['gt_class_ids']), "{} {}".format(result['gt_handle_visibility'], result['gt_class_ids'])


            if type(result) is list:
                final_results += result
            elif type(result) is dict:
                final_results.append(result)
            else:
                assert False

        aps = utils.compute_degree_cm_mAP(final_results, synset_names, log_dir,
                                                                    degree_thresholds = [5, 20 , 30, 50, 70, 90],#range(0, 61, 1), 
                                                                    shift_thresholds= [5, 20, 30,  50, 70, 100,150], #np.linspace(0, 1, 31)*15, 
                                                                    iou_3d_thresholds=np.linspace(0, 1, 101),
                                                                    iou_pose_thres=0.1,
                                                                    use_matches_for_pose=True)
       
    


   