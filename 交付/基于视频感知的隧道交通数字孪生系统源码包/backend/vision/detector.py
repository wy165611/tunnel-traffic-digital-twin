import time
import os
import cv2
import numpy as np
import torch
from torchvision.models.detection import ssdlite320_mobilenet_v3_large
from torchvision.ops import batched_nms
from backend.settings import DATA
from backend.vision.weights import verified_weight

VEHICLE_CLASSES = {3: 'car', 4: 'motorcycle', 6: 'bus', 8: 'truck'}


class VehicleDetector:
    """Pretrained detection adapters; no training or generated observations."""
    def __init__(self, config):
        self.config = config
        device = config['device']
        self.device = 'cuda' if device == 'auto' and torch.cuda.is_available() else ('cpu' if device == 'auto' else device)
        if self.device.startswith('cuda') and not torch.cuda.is_available():
            self.device = 'cpu'
        torch.set_num_threads(config.get('cpu_threads', 4))
        torch.hub.set_dir(str(DATA / 'models'))
        self.model_name = config['model']
        if self.model_name == 'ssdlite320_mobilenet_v3_large':
            weight_file = verified_weight('checkpoints/ssdlite320_mobilenet_v3_large_coco-a79551df.pth')
            self.model = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=91)
            self.model.load_state_dict(torch.load(weight_file, map_location='cpu', weights_only=True))
            self.model = self.model.to(self.device).eval()
            self.class_names = VEHICLE_CLASSES
            self.backend = 'torchvision'
        else:
            config_dir = DATA / 'models' / 'ultralytics-config'
            config_dir.mkdir(exist_ok=True)
            os.environ.setdefault('YOLO_CONFIG_DIR', str(config_dir))
            from ultralytics import YOLO
            if self.model_name == 'visdrone_yolo11n':
                weight_file = verified_weight('visdrone-yolo11n.pt')
                self.class_names = {3:'car', 4:'car', 5:'truck', 8:'bus', 9:'motorcycle'}
            elif self.model_name == 'coco_yolo11n':
                weight_file = verified_weight('yolo11n.pt')
                self.class_names = {2:'car', 3:'motorcycle', 5:'bus', 7:'truck'}
            else:
                raise ValueError('不支持的模型，请使用 visdrone_yolo11n、coco_yolo11n 或 ssdlite320_mobilenet_v3_large')
            self.model = YOLO(str(weight_file))
            self.backend = 'ultralytics'
        self.detect_ms = 0.

    @staticmethod
    def starts(length, tile, overlap):
        if length <= tile:
            return [0]
        step = max(1, int(tile * (1 - overlap)))
        return sorted(set([*range(0, length - tile + 1, step), length - tile]))

    @torch.inference_mode()
    def detect(self, frame):
        started = time.perf_counter()
        h, w = frame.shape[:2]
        size = int(self.config['tile_size'])
        overlap = self.config['tile_overlap']
        tiles = [(x, y, frame[y:y+size, x:x+size])
                 for y in self.starts(h, size, overlap)
                 for x in self.starts(w, size, overlap)] if self.config['tiled'] else [(0, 0, frame)]
        boxes, scores, labels = [], [], []
        for x, y, tile in tiles:
            if self.backend == 'ultralytics':
                result = self.model.predict(tile, imgsz=self.config['input_size'], conf=self.config['confidence'],
                    classes=list(self.class_names), device=self.device, verbose=False, agnostic_nms=True)[0].boxes
                b = result.xyxy.cpu()
                s, l = result.conf.cpu(), result.cls.cpu().to(torch.int64)
            else:
                tensor = torch.from_numpy(cv2.cvtColor(tile, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float().to(self.device) / 255
                result = self.model([tensor])[0]
                keep = (result['scores'] >= self.config['confidence']) & torch.isin(result['labels'], torch.tensor(list(VEHICLE_CLASSES), device=self.device))
                b = result['boxes'][keep].cpu()
                s, l = result['scores'][keep].cpu(), result['labels'][keep].cpu()
            b += torch.tensor([x, y, x, y])
            boxes.extend(b.tolist())
            scores.extend(s.tolist())
            labels.extend(l.tolist())
        detections = []
        if boxes:
            b = torch.tensor(boxes)
            s = torch.tensor(scores)
            # Class agnostic NMS: tile disagreements must not duplicate one vehicle.
            keep = batched_nms(b, s, torch.zeros(len(b), dtype=torch.int64), self.config['nms_iou'])
            for i in keep.tolist():
                box = np.clip(b[i].numpy(), [0, 0, 0, 0], [w, h, w, h])
                if box[2] > box[0] and box[3] > box[1]:
                    detections.append(dict(box=box, confidence=scores[i], type=self.class_names[labels[i]]))
        self.detect_ms = (time.perf_counter() - started) * 1000
        return detections
